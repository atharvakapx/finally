<#
.SYNOPSIS
    Stop the FinAlly Docker container on Windows.
.DESCRIPTION
    Stops and removes the running container. The db volume (bind mount)
    is left untouched so data persists across restarts.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$ContainerName = 'finally'

$existing = docker ps -a -q -f "name=^${ContainerName}$"
if ($existing) {
    Write-Host 'Stopping FinAlly...'
    docker stop $ContainerName 2>$null | Out-Null
    docker rm   $ContainerName 2>$null | Out-Null
    Write-Host 'Stopped.'
} else {
    Write-Host 'FinAlly is not running.'
}
