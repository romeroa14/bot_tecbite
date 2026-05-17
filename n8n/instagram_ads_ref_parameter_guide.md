# Guía: Configuración del Parámetro `ref` en Meta Ads Manager

## Propósito
El parámetro `ref` en Instagram Ads permite que el agente conversacional de Tecbite identifique el contexto del anuncio que el usuario clickeó. Esto mejora significativamente la calidad de respuesta cuando el cliente pregunta por "precio" o "stock" sin especificar el producto.

## ¿Qué es el Parámetro `ref`?

El parámetro `ref` (reference) es un campo opcional que puedes agregar a la URL de tu anuncio de Instagram. Cuando un usuario hace clic en el anuncio y abre una conversación en Instagram Direct, Instagram incluye este valor en el webhook payload bajo `messaging.referral.ref`.

## Estructura del Webhook

```json
{
  "entry": [{
    "messaging": [{
      "referral": {
        "ref": "TU_VALOR_REF",
        "ad_id": "123456789",
        "source": "ADS"
      }
    }]
  }]
}
```

## Formato Recomendado para `ref`

Usa un formato descriptivo y estructurado que el LLM pueda interpretar fácilmente:

### Ejemplos de Valores `ref`:

```
THULE-BIKE-RACK-HILUX-2024
WT-FLOORLINER-TOYOTA-HIGHLANDER
THULE-CARGO-CARRIER-GENERIC
WT-DEFLECTOR-WINDOW-GENERIC
THULE-LUGGAGE-REVO-ESPAÑA
```

### Componentes Sugeridos:

1. **Marca**: `THULE` o `WT` (WeatherTech)
2. **Categoría**: `BIKE-RACK`, `FLOORLINER`, `CARGO-CARRIER`, `DEFLECTOR`, `LUGGAGE`
3. **Vehículo (opcional)**: `HILUX-2024`, `TOYOTA-HIGHLANDER`, `GENERIC`
4. **Variante (opcional)**: `REVO`, `ESPAÑA`, `PREMIUM`

## Cómo Configurar en Meta Ads Manager

### Paso 1: Crear o Editar el Anuncio

1. Accede a [Meta Ads Manager](https://www.facebook.com/adsmanager)
2. Navega a tu cuenta y selecciona la campaña
3. Crea un nuevo anuncio o edita uno existente

### Paso 2: Configurar el Botón de Mensaje

1. En la sección "Call to Action", selecciona "Send Message"
2. Elige "Instagram" como plataforma de destino
3. Verifica que el tipo de mensaje sea "Instagram Direct"

### Paso 3: Agregar el Parámetro `ref`

**Método A: Usar el Generador de URL de Meta**

1. En la configuración del anuncio, busca la sección "URL Parameters" o "Parameters"
2. Agrega `ref` como clave y tu valor descriptivo como valor
3. Ejemplo:
   - Key: `ref`
   - Value: `THULE-BIKE-RACK-HILUX-2024`

**Método B: Manual en la URL del Anuncio**

1. En la configuración del anuncio, ve a "Destination URL"
2. Agrega el parámetro al final de la URL:
   ```
   https://instagram.com/tu_negocio?ref=THULE-BIKE-RACK-HILUX-2024
   ```

### Paso 4: Configurar el Webhook de Instagram

El workflow de n8n ya está configurado para capturar `referral.ref`. Verifica que:

1. El webhook esté activo en tu cuenta de Instagram Business
2. La URL del webhook apunte a tu instancia de n8n:
   ```
   https://n8n.yavingos.com/webhook/instagram-webhook
   ```
3. Los permisos del webhook incluyen:
   - `messages`
   - `messaging_postbacks`
   - `messaging_referrals`

## Validación

### Probar que el Parámetro Funciona

1. Crea un anuncio de prueba con `ref=TEST-VALUE-123`
2. Simula un clic (o usa el "Test Event" de Meta)
3. Abre una conversación en Instagram
4. Envía un mensaje: "precio"
5. Revisa el workflow de n8n:
   - En el nodo `Filter & Normalize`, verifica que `ad_ref` contenga `TEST-VALUE-123`
   - En el nodo `Prepare DeepSeek Request`, verifica que el system prompt incluya el contexto del anuncio

### Ver en el Workflow de n8n

1. Abre el workflow "Tecbite AI Agent - Gran Workflow v6"
2. Ejecuta el nodo `Filter & Normalize` manualmente con un payload de prueba
3. Verifica el output JSON:
   ```json
   {
     "user_id": "123456789",
     "message_text": "precio",
     "ad_ref": "THULE-BIKE-RACK-HILUX-2024",
     "ad_id": "987654321",
     "ad_source": "ADS"
   }
   ```

## Impacto en el Agente

### Sin `ref` (antes):
```
Usuario: "precio"
Agente: "¿Sobre qué producto quieres saber el precio?"
```

### Con `ref=THULE-BIKE-RACK-HILUX-2024` (después):
```
Usuario: "precio"
Agente: "El portabicicletas Thule para Toyota Hilux 2024 cuesta $XXX y está en stock."
```

El agente usa el valor de `ref` para inferir el producto y responder directamente sin preguntar.

## Mejores Prácticas

1. **Consistencia**: Usa un formato consistente para todos los anuncios
2. **Legibilidad**: Usa guiones `-` en lugar de espacios o guiones bajos
3. **Especificidad**: Sé específico pero flexible. `GENERIC` funciona para anuncios de categoría general
4. **Documentación**: Mantén un registro de qué `ref` corresponde a cada anuncio
5. **Testing**: Prueba cada nuevo valor de `ref` antes de lanzar el anuncio

## Troubleshooting

### El parámetro no aparece en el webhook

- Verifica que el anuncio esté configurado con "Send Message" → "Instagram Direct"
- Confirma que el webhook tiene permisos para `messaging_referrals`
- Asegúrate de que el anuncio esté activo

### El agente no usa el contexto del anuncio

- Verifica que el nodo `Prepare DeepSeek Request` incluya `adContext` en el system prompt
- Confirma que `ad_ref` se propaga a través de todos los nodos del workflow
- Revisa los logs de n8n para ver el valor de `ad_ref` en cada nodo

## Referencias

- [Meta Ads Manager Documentation](https://www.facebook.com/business/help)
- [Instagram Messaging API](https://developers.facebook.com/docs/messenger-platform/instagram)
- [n8n Workflow Documentation](https://docs.n8n.io)
