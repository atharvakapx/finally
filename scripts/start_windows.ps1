param([switch]$Build)
$Image = "finally"
$Container = "finally"

# Build if image doesn't exist or --Build flag passed
if ($Build -or !(docker image inspect $Image 2>$null)) {
    Write-Host "Building $Image image..."
    docker build -t $Image "$PSScriptRoot\.."
}

# Stop existing container if running
docker rm -f $Container 2>$null

# Run
docker run -d `
    --name $Container `
    -v "${PWD}/db:/app/db" `
    -p 8000:8000 `
    --env-file .env `
    $Image

Write-Host "FinAlly running at http://localhost:8000"
