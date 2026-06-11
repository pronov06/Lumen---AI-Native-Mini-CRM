import { useEffect, useRef, useState } from "react";
import { WS_BASE } from "./api";
import type { FeedEvent } from "./types";

const MAX_EVENTS = 240;

export interface FeedState {
  connected: boolean;
  events: FeedEvent[];
  total: number;
}

/**
 * Subscribes to /ws/feed and keeps a bounded, newest-first buffer of events.
 * Reconnects with backoff if the socket drops. `onEvent` fires for every event
 * so screens can fold them into their own state (e.g. live funnel counts).
 */
export function useFeed(onEvent?: (e: FeedEvent) => void): FeedState {
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const [total, setTotal] = useState(0);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;
    let retry = 0;
    let timer: number | undefined;

    const connect = () => {
      ws = new WebSocket(`${WS_BASE}/ws/feed`);
      ws.onopen = () => {
        retry = 0;
        setConnected(true);
      };
      ws.onclose = () => {
        setConnected(false);
        if (closed) return;
        retry = Math.min(retry + 1, 6);
        timer = window.setTimeout(connect, 250 * 2 ** (retry - 1));
      };
      ws.onerror = () => ws?.close();
      ws.onmessage = (msg) => {
        let e: FeedEvent;
        try {
          e = JSON.parse(msg.data);
        } catch {
          return;
        }
        if (e.type !== "communication.updated") return;
        onEventRef.current?.(e);
        setTotal((t) => t + 1);
        setEvents((prev) => [e, ...prev].slice(0, MAX_EVENTS));
      };
    };

    connect();
    return () => {
      closed = true;
      if (timer) window.clearTimeout(timer);
      ws?.close();
    };
  }, []);

  return { connected, events, total };
}
