# Script para desplegar Mar-IA-Jose en Azure Container Apps
# Requiere: Azure CLI, Docker

# Configuración
$acrName = "mariajoseai"
$acrLoginServer = "$acrName.azurecr.io"
$imageName = "mariajose"
$resourceGroup = "mariajoseai"
$location = "westeurope"
$containerAppName = "mariajoseai"
$containerAppEnvName = "mariajoseaienv"
$storageAccountName = "mariajoseaistorage"
$fileShareName = "mariajoseaishare"

# Función para obtener la siguiente versión
function Get-NextVersion {
    param (
        [string]$acrName,
        [string]$imageName
    )
    
    # Obtener todas las versiones existentes
    $tags = az acr repository show-tags --name $acrName --repository $imageName --output json 2>$null | ConvertFrom-Json
    
    if (-not $tags -or $tags.Count -eq 0) {
        return "1.0.0"
    }
    
    # Filtrar solo las versiones semánticas válidas
    $versionTags = $tags | Where-Object { $_ -match '^\d+\.\d+\.\d+$' }
    
    if (-not $versionTags -or $versionTags.Count -eq 0) {
        return "1.0.0"
    }
    
    # Encontrar la versión más alta
    $highestVersion = $versionTags | ForEach-Object {
        [System.Version]$_
    } | Sort-Object -Descending | Select-Object -First 1
    
    # Incrementar la versión minor
    $newVersion = [System.Version]::new($highestVersion.Major, $highestVersion.Minor + 1, 0)
    return $newVersion.ToString()
}

# Iniciar sesión en Azure
Write-Host "Iniciando sesión en Azure..." -ForegroundColor Cyan
#az login

# Verificar si el grupo de recursos existe, si no, crearlo
$rgExists = az group exists --name $resourceGroup
if ($rgExists -eq "false") {
    Write-Host "Creando grupo de recursos $resourceGroup..." -ForegroundColor Cyan
    az group create --name $resourceGroup --location $location
}

# Verificar si el ACR existe, si no, crearlo
$acrExists = az acr show --name $acrName --resource-group $resourceGroup 2>$null
if (-not $acrExists) {
    Write-Host "Creando Azure Container Registry $acrName..." -ForegroundColor Cyan
    az acr create --resource-group $resourceGroup --name $acrName --sku Basic
    az acr update -n $acrName --admin-enabled true
}

# Iniciar sesión en el ACR
Write-Host "Iniciando sesión en el ACR..." -ForegroundColor Cyan
az acr login --name $acrName

# Obtener la siguiente versión
$nextVersion = Get-NextVersion -acrName $acrName -imageName $imageName
Write-Host "Nueva versión: $nextVersion" -ForegroundColor Green

# Construir la imagen Docker
Write-Host "Construyendo imagen Docker..." -ForegroundColor Cyan
docker build -t "$imageName`:$nextVersion" .

# Etiquetar la imagen para el ACR
Write-Host "Etiquetando imagen para ACR..." -ForegroundColor Cyan
docker tag "$imageName`:$nextVersion" "$acrLoginServer/$imageName`:$nextVersion"
docker tag "$imageName`:$nextVersion" "$acrLoginServer/$imageName`:latest"

# Subir la imagen al ACR
Write-Host "Subiendo imagen al ACR..." -ForegroundColor Cyan
docker push "$acrLoginServer/$imageName`:$nextVersion"
docker push "$acrLoginServer/$imageName`:latest"

# Crear cuenta de almacenamiento para los volúmenes persistentes
$storageExists = az storage account show --name $storageAccountName --resource-group $resourceGroup 2>$null
if (-not $storageExists) {
    Write-Host "Creando cuenta de almacenamiento para volúmenes persistentes..." -ForegroundColor Cyan
    az storage account create --name $storageAccountName --resource-group $resourceGroup --location $location --sku Standard_LRS
}

# Obtener la clave de la cuenta de almacenamiento
$storageKey = az storage account keys list --account-name $storageAccountName --resource-group $resourceGroup --query "[0].value" -o tsv

# Crear file shares para los volúmenes
$shares = @("uploads", "vectordb", "data", "instance")
foreach ($share in $shares) {
    $shareExists = az storage share exists --name "$fileShareName-$share" --account-name $storageAccountName --account-key $storageKey --query "exists" -o tsv
    if ($shareExists -eq "false") {
        Write-Host "Creando file share para $share..." -ForegroundColor Cyan
        az storage share create --name "$fileShareName-$share" --account-name $storageAccountName --account-key $storageKey
    }
}

# Verificar si el entorno de Container Apps existe
$envExists = az containerapp env show --name $containerAppEnvName --resource-group $resourceGroup 2>$null
if (-not $envExists) {
    Write-Host "Creando entorno de Container Apps..." -ForegroundColor Cyan
    az containerapp env create --name $containerAppEnvName --resource-group $resourceGroup --location $location
}

# Configurar los Azure Files en el Container App Environment
Write-Host "Configurando Azure Files en el Container App Environment..." -ForegroundColor Cyan
foreach ($share in $shares) {
    Write-Host "Configurando storage $share en el environment..." -ForegroundColor Cyan
    $storageCommand = "az containerapp env storage set --name $containerAppEnvName --resource-group $resourceGroup --storage-name $share --azure-file-account-name $storageAccountName --azure-file-account-key `"$storageKey`" --azure-file-share-name `"$fileShareName-$share`" --access-mode ReadWrite"
    Invoke-Expression $storageCommand
}

# Leer variables de entorno del docker-compose.yml
$envVars = @()
$composeFile = Get-Content "d:\repos\Mar-IA-Jose\docker-compose.yml" -Raw
$envMatch = [regex]::Matches($composeFile, '- ([^=]+)=([^\r\n]+)')
foreach ($match in $envMatch) {
    $key = $match.Groups[1].Value.Trim()
    $value = $match.Groups[2].Value.Trim()
    # Escapar las comillas en los valores
    $value = $value.Replace('"', '\"')
    # Encerrar el valor en comillas dobles para manejar espacios y caracteres especiales
    $envVars += "--env-vars `"$key=$value`""
}

# Crear o actualizar la Container App
$containerAppExists = az containerapp show --name $containerAppName --resource-group $resourceGroup 2>$null

if (-not $containerAppExists) {
    Write-Host "Paso 1: Creando Container App básica..." -ForegroundColor Cyan
    # Obtener credenciales del ACR
    $acrPassword = az acr credential show --name $acrName --query 'passwords[0].value' -o tsv
    
    # Crear la Container App con configuración básica
    $createCommand = "az containerapp create --name $containerAppName --resource-group $resourceGroup --environment $containerAppEnvName --image $acrLoginServer/$imageName`:$nextVersion --target-port 80 --ingress external --registry-server $acrLoginServer --registry-username $acrName --registry-password `"$acrPassword`" --cpu 1 --memory 2Gi"
    
    Invoke-Expression $createCommand
    
    # Paso 2: Configurar volúmenes
    Write-Host "Paso 2: Configurando volúmenes en la Container App..." -ForegroundColor Cyan
    
    # Preparar los montajes de volúmenes
    foreach ($share in $shares) {
        Write-Host "Configurando montaje para $share..." -ForegroundColor Cyan
        $mountCommand = "az containerapp update --name $containerAppName --resource-group $resourceGroup --mount-type azure-file --mount-name $share --mount-path /app/$share --share-name $fileShareName-$share --storage-name $storageAccountName"
        Invoke-Expression $mountCommand
    }
    
    # Paso 3: Configurar variables de entorno
    Write-Host "Paso 3: Configurando variables de entorno..." -ForegroundColor Cyan
    
    # Crear un archivo temporal para las variables de entorno
    $envFile = [System.IO.Path]::GetTempFileName()
    $composeFile = Get-Content "d:\repos\Mar-IA-Jose\docker-compose.yml" -Raw
    $envMatch = [regex]::Matches($composeFile, '- ([^=]+)=([^\r\n]+)')
    
    # Construir el comando para actualizar las variables de entorno
    $envVarsCommand = "az containerapp update --name $containerAppName --resource-group $resourceGroup"
    
    foreach ($match in $envMatch) {
        $key = $match.Groups[1].Value.Trim()
        $value = $match.Groups[2].Value.Trim()
        $envVarsCommand += " --set-env-vars `"$key=$value`""
    }
    
    # Ejecutar el comando para actualizar las variables de entorno
    Invoke-Expression $envVarsCommand
} else {
    Write-Host "Actualizando Container App existente..." -ForegroundColor Cyan
    
    # Actualizar la imagen
    Write-Host "Paso 1: Actualizando imagen de la Container App..." -ForegroundColor Cyan
    $updateImageCommand = "az containerapp update --name $containerAppName --resource-group $resourceGroup --image $acrLoginServer/$imageName`:$nextVersion"
    Invoke-Expression $updateImageCommand
    
    # Actualizar los montajes de volúmenes
    Write-Host "Paso 2: Actualizando montajes de volúmenes..." -ForegroundColor Cyan
    foreach ($share in $shares) {
        Write-Host "Configurando montaje para $share..." -ForegroundColor Cyan
        $mountCommand = "az containerapp update --name $containerAppName --resource-group $resourceGroup --mount-type azure-file --mount-name $share --mount-path /app/$share --share-name $fileShareName-$share --storage-name $storageAccountName"
        Invoke-Expression $mountCommand
    }
    
    # Actualizar variables de entorno
    Write-Host "Paso 3: Actualizando variables de entorno..." -ForegroundColor Cyan
    $envVarsCommand = "az containerapp update --name $containerAppName --resource-group $resourceGroup"
    
    $composeFile = Get-Content "d:\repos\Mar-IA-Jose\docker-compose.yml" -Raw
    $envMatch = [regex]::Matches($composeFile, '- ([^=]+)=([^\r\n]+)')
    
    foreach ($match in $envMatch) {
        $key = $match.Groups[1].Value.Trim()
        $value = $match.Groups[2].Value.Trim()
        $envVarsCommand += " --set-env-vars `"$key=$value`""
    }
    
    # Ejecutar el comando para actualizar las variables de entorno
    Invoke-Expression $envVarsCommand
}

Write-Host "¡Despliegue completado con éxito!" -ForegroundColor Green
Write-Host "URL de la aplicación: $(az containerapp show --name $containerAppName --resource-group $resourceGroup --query properties.configuration.ingress.fqdn -o tsv)" -ForegroundColor Green