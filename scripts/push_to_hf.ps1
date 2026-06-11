# push_to_hf.ps1
# Pushes the project to Hugging Face Spaces with the required YAML config
# prepended to README.md (without polluting the GitHub README).

param(
    [string]$Token = ""
)

if (-not $Token) {
    $Token = Read-Host "Enter your Hugging Face token"
}

$HF_YAML = @"
---
title: Lumen AI Native Mini CRM
emoji: rocket
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: true
license: mit
short_description: AI-native CRM with Gemini co-pilot and live delivery feed
tags:
  - crm
  - gemini
  - fastapi
  - react
  - nlp
---

"@

Write-Host "Preparing Hugging Face push..." -ForegroundColor Cyan

# Backup original README
$original = Get-Content README.md -Raw -Encoding UTF8

# Prepend HF YAML config
$hfReadme = $HF_YAML + $original
[System.IO.File]::WriteAllText("$PWD\README.md", $hfReadme, [System.Text.Encoding]::UTF8)

Write-Host "Pushing to Hugging Face Spaces..." -ForegroundColor Cyan
git add README.md
git commit -m "chore: hf deploy - add Space config to README" --allow-empty
git push "https://pronov06:$Token@huggingface.co/spaces/pronov06/lumen-crm" main --force

# Restore original README
[System.IO.File]::WriteAllText("$PWD\README.md", $original, [System.Text.Encoding]::UTF8)
git add README.md
git commit -m "chore: restore clean README after HF push" --allow-empty

Write-Host "Done! HF Space updated. GitHub README unchanged." -ForegroundColor Green
