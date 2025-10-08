$tenantId="cce992e5-26d0-46df-8591-bdd15d5ef494"
$acrName="mariajose"
$version=Get-Date -Format 'yyyyMMddHHmm'
echo $version > version.txt

$containerName="mar-ia-jose"
$repository=

$ImageName="$acrName.azurecr.io/$($containerName):$version"
$ImageNameLatest="$acrName.azurecr.io/$($containerName):latest"

az login --tenant $tenantId
az acr login --name $acrName
docker build -t $ImageName .
docker tag $ImageName $ImageNameLatest
docker push $ImageName
docker push $ImageNameLatest