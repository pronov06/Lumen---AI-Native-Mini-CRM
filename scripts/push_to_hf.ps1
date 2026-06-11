# push_to_hf.ps1
# Pushes the project to Hugging Face Spaces with the required YAML config
# prepended to README.md (without polluting the GitHub README).

param(
    [string]$Token = ""
)

if (-not $Token) {
    $Token = Read-Host "Enter your Hugging Face token"
}

$emoji = [System.Char]::ConvertFromUtf32(0x1F680)  # 🚀 rocket
$HF_YAML = "---`ntitle: Lumen AI Native Mini CRM`nemoji: $emoji`ncolorFrom: indigo`ncolorTo: purple`nsdk: docker`napp_port: 7860`npinned: true`nlicense: mit`nshort_description: AI-native CRM with Gemini co-pilot and live delivery feed`ntags:`n  - crm`n  - gemini`n  - fastapi`n  - react`n  - nlp`n---`n`n"

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
