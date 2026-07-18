# Detached, self-healing runner for the xlkg experiment matrix.
# Started via Start-Process so it survives the Claude session entirely.
# Log: D:\xlkg-data\matrix-run.log   Stop it: stop-matrix.flag in D:\xlkg-data
# Contact email for the Wikidata User-Agent lives OUTSIDE the repo
# (double-blind: no identifying strings in tracked files).
$env:XLKG_CONTACT = (Get-Content "D:\xlkg-data\contact.txt" -ErrorAction SilentlyContinue | Select-Object -First 1)
# Progress lines contain Indic text; redirected stdout defaults to cp1252 and
# crashes the run (UnicodeEncodeError, seen 2026-07-17). Force UTF-8.
$env:PYTHONUTF8 = "1"
Set-Location "D:\Research\xlkg\src"
$log = "D:\xlkg-data\matrix-run.log"
$flag = "D:\xlkg-data\stop-matrix.flag"
Add-Content $log "`n=== runner (re)started $(Get-Date -Format o) ==="
for ($i = 1; $i -le 50; $i++) {
    if (Test-Path $flag) { Add-Content $log "stop flag seen, exiting."; break }
    python run_matrix.py --dataset D:\xlkg-data\gold\all_test.jsonl `
        --models qwen3-8b,llama31-8b --arms direct,pivot,english `
        --run-id main-v1 --property-inventory D:\xlkg-data\gold\property_inventory.json `
        *>> $log
    if ($LASTEXITCODE -eq 0) { Add-Content $log "MATRIX COMPLETE $(Get-Date -Format o)"; break }
    Add-Content $log "attempt $i exited $LASTEXITCODE at $(Get-Date -Format o); retry in 120s"
    Start-Sleep -Seconds 120
}
