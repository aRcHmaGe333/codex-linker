Set-StrictMode -Version Latest
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repo

$tree = (Get-Content .\.ipclaim_tree -Raw).Trim()
$date = (Get-Content .\.ipclaim_date -Raw).Trim()
$author = 'Slavko Stojnić'

Copy-Item -Force 'IPClaim\\LICENSE-APC.md' 'LICENSE-APC.md'
Copy-Item -Force 'IPClaim\\VERIFY.md' 'VERIFY.md'
New-Item -ItemType Directory -Force -Path '.github\\workflows' | Out-Null
Copy-Item -Force 'IPClaim\\.github\\workflows\\timestamp.yml' '.github\\workflows\\timestamp.yml'

$text = Get-Content 'LICENSE-APC.md' -Raw
$text = $text.Replace('[AUTHOR NAME OR ENTITY]',$author)
$text = $text.Replace('[AUTHOR NAME]',$author)
$text = $text.Replace('[INSERT ROOT HASH]',$tree)
$text = $text.Replace('[INSERT TREE HASH]',$tree)
$text = $text.Replace('[INSERT HASH]',$tree)
$text = $text.Replace('[HASH]',$tree)
$text = $text.Replace('[INSERT DATE AND TIME UTC]',$date)
$text = $text.Replace('[INSERT DATE UTC]',$date)
$text = $text.Replace('[YEAR]', (Get-Date).ToUniversalTime().Year.ToString())

Set-Content 'LICENSE-APC.md' -Value $text

# Stage all new/updated files and commit
git add -A
try {
	git commit -m '[APC] IPClaim stamp applied - LICENSE-APC.md'
} catch {
	Write-Output 'No new changes to commit or commit failed.'
}
