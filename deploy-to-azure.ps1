# Script para desplegar Mar-IA-Jose en Azure
# Requiere: Azure CLI, Docker

$ErrorActionPreference = "Stop" # Detener en caso de error

# Deploy Configuratin Parameters
$acrName = "<acr-name>" # update with your Azure Container Registry name (must be unique across Azure)
$imageName = "<container-name>" #update with your container name (can be anyone)
$resourceGroup = "<resource-group-name>" # update with your resource group name
$webAppName = "<web-app-name>" # update with your Web App name (must be unique across Azure)
$location = "northeurope" # update with your preferred Azure region
$skuName = "B1" # update with your preferred App Service plan SKU (B1 is a basic plan, enough for testing and single user) 
$storageAccountName = "<storage-account-name>" # update with your storage account name (must be unique across Azure)

# Model Parameters
$gpt_endpoint="<azure-OpenAI-endpoint>" # update with your Azure OpenAI endpoint
$gpt_api_key="<Azure-OpenAI-api-key>" # update with your Azure OpenAI API key   
$gpt_deployment="gpt-4.1" # update with your Azure OpenAI deployment name
$gpt_api_version="2025-01-01-preview" # update with your Azure OpenAI API version

$embedding_endpoint="<azure-OpenAI-embedding-endpoint>" # update with your Azure OpenAI embedding endpoint
$embedding_api_key="<Azure-OpenAI-embedding-api-key>" # update with your Azure OpenAI embedding API key
$embedding_deployment="text-embedding-3-large" # update with your Azure OpenAI embedding deployment name
$embedding_api_version="2023-05-15" # update with your Azure OpenAI embedding API version

# Constants
$acrLoginServer = "$acrName.azurecr.io"
$shares = @("data") 

# Función para manejar errores y salir del script
function Handle-Error {
    param (
        [string]$ErrorMessage
    )
    
    Write-Host "ERROR: $ErrorMessage" -ForegroundColor Red
    exit 1
}

# Función para cargar variables de entorno desde el archivo .env
function Get-EnvVariables {
    param (
        [string]$EnvFilePath = ".\.env"
    )

    $envSettings = @()
    
    if (Test-Path $EnvFilePath) {
        Write-Host "Cargando variables de entorno desde $EnvFilePath..." -ForegroundColor Cyan
        $envFileContent = Get-Content $EnvFilePath

        foreach ($line in $envFileContent) {
            # Ignorar líneas vacías o comentarios
            if (-not [string]::IsNullOrWhiteSpace($line) -and -not $line.StartsWith('#')) {
                $envSettings += $line
            }
        }
        
        return $envSettings
    } else {
        Write-Host "Archivo .env no encontrado en $EnvFilePath. Se usarán valores predeterminados." -ForegroundColor Yellow
        return $null
    }
}

# Función para obtener la última versión y calcular la siguiente
function Get-NextVersion {

    $versionFile = ".\version.txt"

    # Verificar si existe el archivo version.txt
    if (Test-Path $versionFile) {
        # Leer la versión actual del archivo
        $currentVersion = Get-Content $versionFile -Raw
        $currentVersion = $currentVersion.Trim()

        # Verificar que la versión tenga formato válido
        if ($currentVersion -match '^\d+\.\d+\.\d+$') {
            # Convertir a objeto Version
            $version = [System.Version]$currentVersion

            # Incrementar el tercer dígito (patch)
            $newVersion = [System.Version]::new($version.Major, $version.Minor, $version.Build + 1)
        } else {
            # Si el formato no es válido, comenzar con 1.0.0
            $newVersion = [System.Version]::new(0, 1, 0)
        }
    } else {
        # Si no existe el archivo, comenzar con 1.0.0
        $newVersion = [System.Version]::new(0, 1, 0)
    }

    # Guardar la nueva versión en el archivo
    $newVersion.ToString() | Out-File $versionFile -Force

    return $newVersion.ToString()
}


# Iniciar sesión en Azure
Write-Host "Benvenido al script de despliegue de Mar-IA-Jose en Azure" -ForegroundColor Green
Write-Host "Asegúrate de tener Azure CLI y Docker instalados y configurados." -ForegroundColor Yellow
Pause
Write-Host "Iniciando sesión en Azure..." -ForegroundColor Cyan
az login

# Verificar si el grupo de recursos existe, si no, crearlo
try {
    $rgExists = az group exists --name $resourceGroup
    if ($rgExists -eq "false") {
        Write-Host "Creando grupo de recursos $resourceGroup..." -ForegroundColor Cyan
        $result = az group create --name $resourceGroup --location $location
        if (-not $result) { Handle-Error "No se pudo crear el grupo de recursos" }
    }
} catch {
    Handle-Error "Error al verificar/crear el grupo de recursos: $_"
}

# Verificar si el ACR existe, si no, crearlo
try {
    $acrExists = az acr check-name --name $acrName --query "nameAvailable" -o tsv
    if ($acrExists -eq "true") {
        Write-Host "Creando Azure Container Registry $acrName..." -ForegroundColor Cyan
        $result = az acr create --resource-group $resourceGroup --name $acrName --sku Basic
        if (-not $result) { Handle-Error "No se pudo crear el Azure Container Registry" }
        
        $result = az acr update -n $acrName --admin-enabled true
        if (-not $result) { Handle-Error "No se pudo habilitar el acceso admin en el ACR" }
    }
} catch {
    Handle-Error "Error al verificar/crear el ACR: $_"
}

# Iniciar sesión en el ACR
Write-Host "Iniciando sesión en el ACR..." -ForegroundColor Cyan
try {
    $result = az acr login --name $acrName
    if (-not $result) { Handle-Error "No se pudo iniciar sesión en el ACR" }
} catch {
    Handle-Error "Error al iniciar sesión en el ACR: $_"
}

# Obtener la siguiente versión
try {
    $nextVersion = Get-NextVersion
    if (-not $nextVersion) { Handle-Error "No se pudo obtener la siguiente versión" }
    Write-Host "Nueva versión: $nextVersion" -ForegroundColor Green
} catch {
    Handle-Error "Error al obtener la siguiente versión: $_"
}

# Construir la imagen Docker
Write-Host "Construyendo imagen Docker..." -ForegroundColor Cyan
try {
    $buildResult = docker build -t "$imageName`:$nextVersion" .
    if ($LASTEXITCODE -ne 0) { Handle-Error "Error al construir la imagen Docker" }
} catch {
    Handle-Error "Error al construir la imagen Docker: $_"
}

# Etiquetar la imagen para el ACR
Write-Host "Etiquetando imagen para ACR..." -ForegroundColor Cyan
try {
    docker tag "$imageName`:$nextVersion" "$acrLoginServer/$imageName`:$nextVersion"
    if ($LASTEXITCODE -ne 0) { Handle-Error "Error al etiquetar la imagen con versión" }
    
    docker tag "$imageName`:$nextVersion" "$acrLoginServer/$imageName`:latest"
    if ($LASTEXITCODE -ne 0) { Handle-Error "Error al etiquetar la imagen como latest" }
} catch {
    Handle-Error "Error al etiquetar la imagen: $_"
}

# Subir la imagen al ACR
Write-Host "Subiendo imagen al ACR..." -ForegroundColor Cyan
try {
    docker push "$acrLoginServer/$imageName`:$nextVersion"
    if ($LASTEXITCODE -ne 0) { Handle-Error "Error al subir la imagen con versión al ACR" }
    
    docker push "$acrLoginServer/$imageName`:latest"
    if ($LASTEXITCODE -ne 0) { Handle-Error "Error al subir la imagen latest al ACR" }
} catch {
    Handle-Error "Error al subir la imagen al ACR: $_"
}

# Crear cuenta de almacenamiento para los volúmenes persistentes
try {
    $storageExists = az storage account show --name $storageAccountName --resource-group $resourceGroup 2>$null
    if (-not $storageExists) {
        Write-Host "Creando cuenta de almacenamiento para volúmenes persistentes..." -ForegroundColor Cyan
        $result = az storage account create --name $storageAccountName --resource-group $resourceGroup --location $location --sku Standard_LRS
        if (-not $result) { Handle-Error "No se pudo crear la cuenta de almacenamiento" }
    }
} catch {
    Handle-Error "Error al verificar/crear la cuenta de almacenamiento: $_"
}

# Obtener la clave de la cuenta de almacenamiento
try {
    $storageKey = az storage account keys list --account-name $storageAccountName --resource-group $resourceGroup --query "[0].value" -o tsv
    if (-not $storageKey) { Handle-Error "No se pudo obtener la clave de la cuenta de almacenamiento" }
} catch {
    Handle-Error "Error al obtener la clave de la cuenta de almacenamiento: $_"
}

# Crear file shares para los volúmenes
foreach ($share in $shares) {
    try {
        $shareExists = az storage share exists --name "$share" --account-name $storageAccountName --account-key $storageKey --query "exists" -o tsv
        if ($shareExists -eq "false") {
            Write-Host "Creando file share para $share..." -ForegroundColor Cyan
            $result = az storage share create --name "$share" --account-name $storageAccountName --account-key $storageKey
            if (-not $result) { Handle-Error "No se pudo crear el file share $share" }
        }
    } catch {
        Handle-Error "Error al verificar/crear el file share $share : $_"
    }
}



# Verificar si la Web App existe
try {
    $webAppExists = az webapp list --resource-group $resourceGroup --query "[?name=='$webAppName']" -o tsv
    
    if (-not $webAppExists) {
        # Crear plan de App Service si no existe
        $planName = "$webAppName-plan"
        $planExists = az appservice plan list --resource-group $resourceGroup --query "[?name=='$planName']" -o tsv

        if (-not $planExists) {
            Write-Host "Creando plan de App Service..." -ForegroundColor Cyan
            $result = az appservice plan create --name $planName --resource-group $resourceGroup --sku $skuName --is-linux
            if (-not $result) { Handle-Error "No se pudo crear el plan de App Service" }
        }

        # Crear la Web App
        Write-Host "Creando Web App..." -ForegroundColor Cyan
        $result = az webapp create --resource-group $resourceGroup --plan $planName --name $webAppName --deployment-container-image-name "$acrLoginServer/$imageName`:$nextVersion"
        if (-not $result) { Handle-Error "No se pudo crear la Web App" }

        # Configurar montaje de los file shares en la Web App
        Write-Host "Configurando montaje de file shares en la Web App..." -ForegroundColor Cyan
        foreach ($share in $shares) {
            try {
                $mountPath = "/app/$share"
                Write-Host "Montando $share en $mountPath..." -ForegroundColor Cyan
                $result = az webapp config storage-account add --resource-group $resourceGroup --name $webAppName `
                    --custom-id "$share-mount" `
                    --storage-type AzureFiles `
                    --account-name $storageAccountName `
                    --share-name "$share" `
                    --access-key $storageKey `
                    --mount-path $mountPath
                if (-not $result) { Handle-Error "No se pudo montar el file share $share" }
            } catch {
                Handle-Error "Error al montar el file share $share : $_"
            }
        }        # Add environment variables
        Write-Host "Configurando variables de entorno adicionales..." -ForegroundColor Cyan
        $envSettings = Get-EnvVariables

        if (-not $envSettings) {
            $envSettings = @(
                "azure_endpoint=$gpt_endpoint" 
                "api_key=$gpt_api_key"
                "model_name=$gpt_deployment" 
                "api_version=$gpt_api_version" 
                "embedding_endpoint=$embedding_endpoint" 
                "embedding_deployment=$embedding_deployment"
                "embedding_api=$embedding_api_version" 
                "embedding_api_key=$embedding_api_key"
            )
        }

        # Apply settings to web app
        Write-Host "Aplicando variables de entorno a la Web App..." -ForegroundColor Cyan
        foreach ($setting in $envSettings) {
            try {
                $result = az webapp config appsettings set --name $webAppName --resource-group $resourceGroup --settings $setting
                if (-not $result) { Handle-Error "No se pudo configurar la variable de entorno: $setting" }
            } catch {
                Handle-Error "Error al configurar la variable de entorno: $_"
            }
        }

        # Configurar la Web App para usar el ACR
        Write-Host "Configurando Web App para usar ACR..." -ForegroundColor Cyan
        try {
            $acrPassword = az acr credential show --name $acrName --query "passwords[0].value" -o tsv
            if (-not $acrPassword) { Handle-Error "No se pudo obtener la contraseña del ACR" }
            
            $result = az webapp config container set --name $webAppName --resource-group $resourceGroup `
                --docker-custom-image-name "$acrLoginServer/$imageName`:$nextVersion" `
                --docker-registry-server-url "https://$acrLoginServer" `
                --docker-registry-server-user $acrName `
                --docker-registry-server-password $acrPassword
            if (-not $result) { Handle-Error "No se pudo configurar el contenedor en la Web App" }
        } catch {
            Handle-Error "Error al configurar el contenedor en la Web App: $_"
        }

    } else {
        # Actualizar la Web App existente
        Write-Host "Actualizando Web App existente..." -ForegroundColor Cyan
        
        # Actualizar variables de entorno
        Write-Host "Actualizando variables de entorno..." -ForegroundColor Cyan
        $envSettings = Get-EnvVariables

        if (-not $envSettings) {
            Write-Host "No se encontró archivo .env. Se usarán valores predeterminados." -ForegroundColor Yellow
            $envSettings = @(
                "azure_endpoint=$gpt_endpoint" 
                "api_key=$gpt_api_key"
                "model_name=$gpt_deployment" 
                "api_version=$gpt_api_version" 
                "embedding_endpoint=$embedding_endpoint" 
                "embedding_deployment=$embedding_deployment"
                "embedding_api=$embedding_api_version" 
                "embedding_api_key=$embedding_api_key"
            )
        }
        
        # Apply settings to web app
        foreach ($setting in $envSettings) {
            try {
                $result = az webapp config appsettings set --name $webAppName --resource-group $resourceGroup --settings $setting
                if (-not $result) { Handle-Error "No se pudo actualizar la variable de entorno: $setting" }
            } catch {
                Handle-Error "Error al actualizar la variable de entorno: $_"
            }
        }
        
        try {
            $acrPassword = az acr credential show --name $acrName --query "passwords[0].value" -o tsv
            if (-not $acrPassword) { Handle-Error "No se pudo obtener la contraseña del ACR" }
            
            $result = az webapp config container set --name $webAppName --resource-group $resourceGroup `
                --docker-custom-image-name "$acrLoginServer/$imageName`:$nextVersion" `
                --docker-registry-server-url "https://$acrLoginServer" `
                --docker-registry-server-user $acrName `
                --docker-registry-server-password $acrPassword
            if (-not $result) { Handle-Error "No se pudo actualizar el contenedor en la Web App" }
        } catch {
            Handle-Error "Error al actualizar el contenedor en la Web App: $_"
        }
    }
} catch {
    Handle-Error "Error al verificar/crear/actualizar la Web App: $_"
}

# Finalizar con éxito
Write-Host "¡Despliegue completado con éxito!" -ForegroundColor Green
Write-Host "URL de la aplicación: https://$webAppName.azurewebsites.net" -ForegroundColor Green
exit 0