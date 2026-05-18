# Setup de Azure Blob Storage

Esta guía configura la cuenta de Azure necesaria para Fase 1B siguiendo
la convención de la wiki (**DG: Gobernabilidad → Gobernabilidad de
Recursos en Azure**).

**Tiempo estimado:** 15 minutos.

---

## Resultado esperado

Al terminar tenés:

| Recurso | Nombre | Región | Notas |
|---|---|---|---|
| Resource Group | `rg-pokegrading-dev` | East US 2 | _Ya existe_ |
| Storage Account | `stpokegradingdev` | East US 2 | Crear ahora |
| Container | `cartas-referencia` | — | Dentro del Storage Account |
| Connection String | (privada) | — | En el `.env` local de cada dev |

> ⚠️ El nombre del Storage Account es **único global** en todo Azure.
> Si `stpokegradingdev` ya está tomado, usá `stpokegradingdev2` o algo similar.
> Documentar el nombre real en este archivo después.

---

## Opción A — Azure Portal (recomendada la primera vez)

### 1. Crear el Storage Account

1. Entrá a https://portal.azure.com con tu cuenta de Azure for Students.
2. Buscá **"Storage accounts"** en la barra superior → **Create**.
3. Configurá la pestaña **Basics**:

   | Campo | Valor |
   |---|---|
   | Subscription | `Azure for Students` (la que corresponda) |
   | Resource group | `rg-pokegrading-dev` *(ya existente)* |
   | Storage account name | `stpokegradingdev` |
   | Region | `(US) East US 2` |
   | Primary service | `Azure Blob Storage or Azure Data Lake Storage Gen 2` |
   | Performance | `Standard` |
   | Redundancy | `Locally-redundant storage (LRS)` |

   > **LRS** es lo más barato (~$0.018/GB/mes) y suficiente para dev.
   > En prod usaremos `ZRS` o `GZRS` por durabilidad.

4. **Advanced** — dejá los defaults.

5. **Networking** — dejá `Enable public access from all networks` (después restringimos en prod).

6. **Data protection** — dejá los defaults.

7. **Tags** — agregá los tags obligatorios de la política:

   | Name | Value |
   |---|---|
   | `environment` | `dev` |
   | `project` | `pokegrading` |

8. **Review + Create** → **Create**. El despliegue toma ~1 minuto.

### 2. Crear el Container

1. Una vez creado el Storage Account, abrilo → menú lateral → **Containers**.
2. **+ Container**:

   | Campo | Valor |
   |---|---|
   | Name | `cartas-referencia` |
   | Anonymous access level | `Private (no anonymous access)` |

3. **Create**.

   > Lo dejamos **privado** porque el acceso a las imágenes lo media
   > el backend. Si en el futuro hace falta servir imágenes directo
   > al frontend, generamos SAS tokens con TTL en vez de hacer público
   > el contenedor.

### 3. Obtener la Connection String

1. En el Storage Account → menú lateral → **Security + networking** → **Access keys**.
2. **Show** en `key1` → copiá el valor de **Connection string**.
3. Pegalo en tu archivo `.env` local:

   ```env
   AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=stpokegradingdev;AccountKey=...;EndpointSuffix=core.windows.net
   AZURE_BLOB_CONTAINER_CARTAS=cartas-referencia
   ```

   > **NUNCA** commitear esa cadena. Está en `.gitignore`. Si por error la pusheás,
   > rotá la key inmediatamente desde el Portal con el botón **Rotate key**.

---

## Opción B — Azure CLI (más rápido si ya repetiste el setup)

Requiere `az` instalado y `az login` hecho.

```bash
# Variables
RG="rg-pokegrading-dev"
LOC="eastus2"
SA="stpokegradingdev"
CONTAINER="cartas-referencia"

# Crear Storage Account
az storage account create \
  --name "$SA" \
  --resource-group "$RG" \
  --location "$LOC" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --access-tier Hot \
  --tags environment=dev project=pokegrading

# Crear container
az storage container create \
  --name "$CONTAINER" \
  --account-name "$SA" \
  --public-access off \
  --auth-mode login

# Obtener connection string (NO compartir por chat o commit)
az storage account show-connection-string \
  --name "$SA" \
  --resource-group "$RG" \
  --query connectionString \
  --output tsv
```

Copiá el output a tu `.env` local.

---

## Verificación

Una vez configurada la connection string, ejecutá:

```bash
cd backend
python -m scripts.verificar_azure
```

Esperás ver:

```
Conectando a Azure Storage...
Listando contenedor 'cartas-referencia'...
  Contenedor 'cartas-referencia' existe y es accesible.
Subiendo blob de prueba '_verificar_azure/test.txt'...
  URL: https://stpokegradingdev.blob.core.windows.net/cartas-referencia/_verificar_azure/test.txt
Verificando existencia...
  OK.
Eliminando blob de prueba...
  OK.

Azure Blob Storage verificado correctamente.
```

Si falla, revisá:
1. Connection string copiada completa (sin saltos de línea ni espacios).
2. El nombre del contenedor en `AZURE_BLOB_CONTAINER_CARTAS` matchea el que creaste.
3. Tu IP no esté bloqueada por firewall del Storage Account (en `Networking`).

---

## Para cada miembro nuevo del equipo

1. Pedile al `Owner` (los founders) que te agregue como `Storage Blob Data Contributor` en el Storage Account.
2. Copiá la connection string a tu `.env` local (vía 1Password / Bitwarden compartido por el equipo, **no por chat**).
3. Corré `python -m scripts.verificar_azure` para confirmar.

---

## Costo esperado

Para Sprint 1 con uso típico de equipo de 4 desarrolladores:

| Concepto | Estimación mensual |
|---|---|
| Almacenamiento (LRS) | ~$0.20 por GB |
| Operaciones (upload + read) | ~$0.05 por 10k ops |
| **Total estimado dev** | **< $5/mes** |

Bien dentro del límite de `$80/mes` para dev del wiki (**DO §7.2**).
