# Meta App Review — Tecbite Asistente Comercial

Documento de justificación de permisos para la revisión de la app **Tecbite Asistente Comercial** (integración Instagram / Facebook / WhatsApp Business de **Tecbite Panamá**, distribuidor oficial Thule y WeatherTech).

**Propósito de la app:** atender consultas de clientes que llegan por Instagram Direct (anuncios y orgánico), identificar vehículo y producto compatible, consultar disponibilidad/precio desde el ERP, y escalar a un asesor humano cuando hace falta. Los leads calificados se registran en Odoo CRM.

**Usuarios finales:** clientes de Tecbite que escriben por Instagram DM.  
**Usuarios internos:** equipo comercial y mercadeo de Tecbite (Odoo, no expuestos en esta app).

**Stack técnico:** webhook Meta → workflow n8n → agente IA con tools de fitment/catálogo → Graph API Instagram Send API → Odoo ERP.

---

## Resumen del flujo (para el video de demostración)

1. Cliente toca anuncio de Instagram y abre conversación en DM.
2. Cliente escribe, por ejemplo: *"Hola, necesito barras para Toyota Corolla 2008"*.
3. El asistente responde con preguntas guiadas (tipo de techo, categoría) y recomienda productos compatibles con stock y precio.
4. Si el cliente elige *WhatsApp* o el bot no puede confirmar compatibilidad, se muestra botón para contactar asesor humano.
5. El lead (vehículo, producto, origen del anuncio) queda registrado en Odoo para seguimiento comercial.

**URL de prueba / webhook:** `https://n8n.yavingos.com/webhook/instagram-webhook`  
**Cuenta Instagram Business:** @TecbitePanama (o la cuenta vinculada al Business Manager de Tecbite).

---

## Textos listos para copiar — campo «Describe cómo tu app usa este permiso»

### instagram_business_basic

**Uso:** Obtenemos el ID y datos básicos de la cuenta profesional de Instagram de Tecbite vinculada a la Página de Facebook, para asociar correctamente los webhooks de mensajes entrantes y enviar respuestas desde la cuenta oficial del negocio.

**Valor para el usuario:** el cliente siempre conversa con la cuenta verificada de Tecbite, no con un perfil genérico.

**Por qué es necesario:** sin este permiso no podemos identificar la cuenta IG Business ni enrutar mensajes al agente de atención.

---

### instagram_business_manage_messages *(permiso principal)*

**Uso:** Es el permiso central de la app. Cuando un cliente envía un mensaje por Instagram Direct:

1. Meta envía el evento al webhook de la app.
2. El agente procesa el mensaje, consulta compatibilidad de productos (barras Thule, alfombras WeatherTech) y responde en el mismo hilo de DM.
3. Si el cliente solicita hablar con un asesor o el sistema detecta un caso que requiere intervención humana, la app envía un mensaje con botón de escalamiento.
4. Los metadatos de la conversación (vehículo, categoría, origen del anuncio) se guardan para seguimiento en Odoo CRM.

**Valor para el usuario:** respuestas inmediatas 24/7 sobre compatibilidad, precio y disponibilidad, sin esperar horario de tienda.

**Por qué es necesario:** toda la funcionalidad de atención automatizada y respuesta en DM depende de leer y enviar mensajes en la cuenta profesional.

**Datos recibidos:** ID del remitente, texto del mensaje, metadatos de referral de anuncio (`ad_id`, `ref`). No usamos el contenido para publicidad de terceros ni reventa de datos.

---

### instagram_basic

**Uso:** Complemento de compatibilidad con la API de Instagram para operaciones de lectura básica del perfil profesional conectado (username, ID) durante la configuración inicial y validación de la cuenta en Business Manager.

**Valor:** garantiza que la integración apunta a la cuenta correcta de Tecbite.

**Por qué es necesario:** requisito de Meta para permisos avanzados de mensajería y comentarios en el ecosistema Instagram Login / Graph API.

---

### instagram_manage_messages

**Uso:** Mismo flujo de atención al cliente descrito en `instagram_business_manage_messages`, en la variante de API requerida por algunos endpoints legacy del webhook de mensajería de Instagram vinculado a Página de Facebook.

**Valor y necesidad:** idénticos al permiso business equivalente; permite recibir webhooks `messages` y enviar respuestas transaccionales de soporte comercial.

---

### instagram_manage_comments

**Uso:** *(Solo si Tecbite activará moderación de comentarios)* Permitirá al equipo comercial ver y responder comentarios en publicaciones de productos (consultas de precio, compatibilidad de vehículo) desde la misma plataforma de atención, derivando a DM cuando la respuesta requiere datos del vehículo del cliente.

**Valor:** respuestas más rápidas en comentarios públicos de anuncios de barras y alfombras.

**Por qué es necesario:** unificar atención pre-venta en Instagram sin que el cliente tenga que repetir información.

> **Nota interna:** si aún no usan comentarios, consideren **eliminar este permiso** de la solicitud hasta implementarlo, para reducir fricción en la revisión.

---

### instagram_business_manage_comments

**Uso:** Igual que `instagram_manage_comments`, en la API Business de Instagram. Lectura de comentarios en publicaciones de la cuenta profesional y respuestas del equipo comercial o del bot cuando detecta preguntas frecuentes de compatibilidad.

**Valor / necesidad:** coherencia de atención omnicanal en la cuenta Business de Tecbite.

---

### whatsapp_business_messaging

**Uso:** Cuando el cliente elige *«Hablar con asesor»* en Instagram DM, la app crea o continúa el contacto en **WhatsApp Business de Tecbite** enviando un mensaje de bienvenida con el contexto del vehículo y producto ya capturado en Instagram (handoff omnicanal). Los asesores continúan la cotización en WhatsApp dentro de la ventana permitida por Meta.

**Valor:** el cliente no repite marca, modelo, año ni producto al pasar de Instagram a WhatsApp.

**Por qué es necesario:** Tecbite unifica ventas en Odoo + WhatsApp Business; este permiso permite el traspaso automático del contexto del lead.

**Tipo de mensajes:** solo respuestas a solicitudes del usuario y mensajes de servicio/utility post-handoff, no spam ni marketing no solicitado.

---

### whatsapp_business_management

**Uso:** Configuración y administración de la cuenta WhatsApp Business de Tecbite en Business Manager: vincular número, plantillas aprobadas de handoff, webhooks de estado de entrega, y sincronización con Odoo CRM.

**Valor:** operación estable del canal WhatsApp para el equipo comercial.

**Por qué es necesario:** sin gestión de la cuenta WABA no podemos registrar el webhook ni enviar mensajes de handoff desde el flujo automatizado.

---

### pages_show_list

**Uso:** Al iniciar sesión, el administrador de Tecbite selecciona la Página de Facebook vinculada a su cuenta Instagram Business. La app lista las Páginas que el usuario administra para conectar el webhook de mensajería correcto.

**Valor:** configuración guiada sin errores de cuenta.

**Por qué es necesario:** prerequisito de Meta para suscribir webhooks de mensajes y metadatos en la Página.

---

### pages_manage_metadata

**Uso:** Suscribimos la Página de Facebook de Tecbite a los campos de webhook necesarios (`messages`, `messaging_postbacks`, `messaging_referrals`) para recibir DMs de Instagram y metadatos de anuncios (`ad_id`, `ref`) cuando el cliente abre chat desde un anuncio.

**Valor:** el agente sabe desde qué producto/anuncio llegó el cliente y responde con contexto.

**Por qué es necesario:** sin suscripción de metadatos no recibimos eventos de mensajería ni referral de ads.

---

### pages_messaging

**Uso:** Envío y recepción de mensajes a través de la Página de Facebook conectada a Instagram Direct (Messenger Platform). La app responde mensajes transaccionales de consulta comercial y botones de quick reply (categorías de producto, tipo de techo, WhatsApp).

**Valor:** experiencia conversacional estructurada en DM.

**Por qué es necesario:** la API de Instagram Messaging opera sobre la infraestructura de Pages Messaging.

#### Instrucciones para reproducir (requerido por Meta)

1. Iniciar sesión en la app con usuario administrador de la Página Tecbite.
2. Enviar mensaje de prueba al Instagram DM de @TecbitePanama desde cuenta de prueba: *"Hola, barras para Hyundai Tucson 2019"*.
3. Verificar respuesta automática con opciones de producto.
4. En Meta Developer → Webhooks, confirmar evento `messages` recibido.
5. En Graph API Explorer, opcional: `POST /{ig-user-id}/messages` con token de página para ver envío saliente.

---

### pages_utility_messaging

**Uso:** Envío de mensajes **utility** (no promocionales) en Messenger/Instagram DM: confirmación de handoff a asesor, aviso de que un humano continuará la conversación, y actualizaciones de estado de cotización solicitadas explícitamente por el cliente.

**Valor:** comunicaciones de servicio claras fuera de ventana promocional.

**Por qué es necesario:** diferenciar mensajes transaccionales de campañas de marketing cumpliendo políticas de Meta.

---

### pages_read_engagement

**Uso:** Lectura de métricas básicas de engagement de la Página (mensajes recibidos, respuestas enviadas) para reportes internos de SLA de atención comercial en Odoo/dashboard interno. Datos agregados para mejorar tiempos de respuesta del agente.

**Valor:** mejora operativa del equipo de ventas.

**Por qué es necesario:** prerequisito de `ads_management` y visibilidad operativa del canal.

**Uso de datos:** solo analytics interno agregado; no se venden datos a terceros.

---

### marketing_messages_messenger

**Uso:** *(Solo si enviarán mensajes de marketing con opt-in)* Envío de mensajes de marketing **solo a usuarios que iniciaron conversación desde anuncio de Instagram y dieron opt-in explícito** (p. ej. botón «Recibir ofertas de accesorios para mi vehículo»). Contenido: promociones de barras Thule y alfombras WeatherTech relacionadas con el vehículo declarado.

**Valor:** ofertas relevantes post-consulta, no mensajes genéricos.

**Por qué es necesario:** campañas de retargeting conversacional autorizadas por el usuario dentro de Messenger/Instagram.

> **Nota interna:** si no tienen opt-in implementado, **eliminen este permiso** antes de enviar la revisión.

---

### catalog_management

**Uso:** Sincronización del catálogo de productos Tecbite (SKUs Thule/WeatherTech, precio, stock) con Meta Commerce Manager para que los anuncios de Instagram muestren productos correctos y el agente pueda referenciar ítems del catálogo en respuestas de DM vinculadas a anuncios de catálogo.

**Valor:** coherencia entre anuncio, catálogo y respuesta del bot.

**Por qué es necesario:** anuncios de producto dinámico y consultas «¿tienen este SKU?» desde creative de catálogo.

---

### business_management

**Uso:** Acceso al Business Manager de Tecbite para asociar la app con la cuenta comercial, asignar la Página, cuenta Instagram Business y WhatsApp Business, y gestionar usuarios del equipo con permisos sobre los activos.

**Valor:** administración centralizada de activos Meta del negocio.

**Por qué es necesario:** despliegue y mantenimiento de la integración en producción.

---

### ads_read

**Uso:** Lectura de metadatos y rendimiento de anuncios de Instagram (`ad_id`, campaña, conjunto) para atribuir conversaciones DM al anuncio de origen y medir conversiones consulta→lead en Odoo. Solo lectura; no modificamos creativos desde esta app.

**Valor:** el equipo de mercadeo sabe qué anuncios generan leads calificados.

**Por qué es necesario:** correlacionar `referral.ad_id` del webhook con campañas reales en Ads Manager.

---

### ads_management

**Uso:** Gestión limitada de campañas publicitarias de Tecbite en Instagram/Facebook relacionadas con el objetivo *Mensajes* y *Conversiones*, desde herramientas internas conectadas a Odoo. Creación/ajuste de conjuntos de anuncios que dirigen tráfico al DM con parámetro `ref` de producto.

**Valor:** alinear anuncios con respuestas automatizadas del agente.

**Por qué es necesario:** prerequisito de `marketing_messages_messenger` y operación integrada ads + atención.

---

### public_profile

**Uso:** Durante login de Facebook del administrador que configura la app, obtenemos nombre e ID público para mostrar «Conectado como [nombre]» en el panel de configuración. No accedemos a datos de clientes finales vía este permiso.

**Valor:** experiencia de configuración clara para el admin de Tecbite.

**Por qué es necesario:** autenticación OAuth estándar de Meta.

---

### email

**Uso:** Durante registro/login del desarrollador/administrador en el flujo OAuth, Meta puede devolver el email verificado de la cuenta Facebook del administrador de Tecbite para identificación de contacto técnico y alertas de la integración.

**Valor:** recuperación de acceso y contacto de soporte.

**Por qué es necesario:** login estándar; no enviamos marketing por email con este permiso.

---

### Human Agent

**Uso:** Cuando un asesor humano de Tecbite toma control de una conversación de Instagram DM (fitment no resuelto, cotización especial, stock dudoso), la app marca el hilo como atendido por humano y permite respuestas del agente **fuera de la ventana estándar de 24 horas**, conforme a la política Human Agent de Meta.

**Valor:** el cliente recibe seguimiento real por un vendedor sin perder el hilo.

**Por qué es necesario:** casos de escalamiento documentados en SLA comercial (handoff por `NO_SQL_FIT`, stock no confirmado, etc.).

**Condiciones de uso:** solo escalamiento a humano real; no automatización disfrazada de humano.

---

### Marketing API Access Tier

**Uso:** Acceso de nivel estándar a Marketing API para lectura/gestión de campañas de mensajes de Tecbite descritas en `ads_read` y `ads_management`. Llamadas de prueba realizadas contra endpoints de insights y ad accounts del Business Manager de Tecbite.

**Valor:** operación publicitaria integrada con atención en DM.

**Por qué es necesario:** tier requerido para escalar uso de Marketing API en producción.

---

### Business Asset User Profile Access

**Uso:** Cuando un miembro del equipo comercial de Tecbite es asignado a un activo (Página, cuenta IG, WABA) en Business Manager, la app puede mostrar nombre/foto de perfil del usuario asignado en logs internos de auditoría («Lead tomado por Juan Pérez») en Odoo.

**Valor:** trazabilidad de quién atiende cada lead.

**Por qué es necesario:** cumplimiento operativo y auditoría interna; no exposición pública de perfiles.

---

## Confirmación de uso permitido (texto genérico)

> Confirmamos que cualquier información recibida a través de [PERMISO] se utilizará **únicamente** para los fines descritos: atención comercial y soporte pre-venta de productos Tecbite solicitados por el propio usuario, mejora operativa interna con datos agregados, y gestión de activos del negocio en Business Manager. **No** vendemos, compartimos con terceros ni usamos datos de mensajes para publicidad no autorizada. Cumplimos las Políticas de la plataforma Meta y las Condiciones del servicio de Instagram/Facebook.

---

## Guía del screencast (1 video por permiso o 1 video maestro reutilizable)

**Duración sugerida:** 2–4 minutos.  
**Idioma:** español.  
**Formato:** MP4, mostrar pantalla + opcional narración.

| Escena | Qué mostrar |
|--------|-------------|
| 1 | Instagram: anuncio o perfil @TecbitePanama → abrir DM |
| 2 | Cliente escribe consulta de producto + vehículo |
| 3 | Respuesta del bot con quick replies (categoría, techo) |
| 4 | Recomendación de producto con precio/stock |
| 5 | Cliente elige «WhatsApp» → botón de handoff |
| 6 | *(Opcional)* WhatsApp Business: mensaje con contexto del vehículo |
| 7 | Meta Developer / n8n: webhook recibiendo evento (sin mostrar tokens) |
| 8 | Odoo: lead creado con origen Instagram + vehículo |

**Importante para revisores:** usar cuenta de **prueba** (Test User) y entorno de desarrollo; ocultar tokens, contraseñas y `.env`.

---

## Preguntas frecuentes de revisión (respuestas sugeridas)

**¿La app es un chatbot?**  
Sí, asistente comercial automatizado con escalamiento obligatorio a humano cuando no hay certeza de compatibilidad o el cliente lo pide.

**¿Recopilan datos sensibles?**  
Solo lo necesario para cotizar: texto del chat, ID de conversación, vehículo declarado, producto de interés y metadatos del anuncio. Se almacena en infraestructura de Tecbite (Postgres/Odoo), no se revende.

**¿Envían mensajes proactivos sin que el usuario escriba primero?**  
No en Instagram DM. En WhatsApp solo post-handoff con contexto de conversación iniciada por el usuario en Instagram.

**¿Por qué tantos permisos?**  
Tecbite opera Instagram Ads → DM → WhatsApp → Odoo. Cada permiso cubre un eslabón (mensajes, página, ads, catálogo, handoff humano).

---

## Permisos recomendados para ELIMINAR si no están implementados

Reducir permisos no usados **aumenta probabilidad de aprobación**:

| Permiso | Eliminar si… |
|---------|----------------|
| `instagram_manage_comments` / `instagram_business_manage_comments` | No responden comentarios desde la app aún |
| `marketing_messages_messenger` | No hay opt-in de marketing en Messenger |
| `catalog_management` | No usan catálogo en Commerce Manager |
| `pages_utility_messaging` | Solo usan mensajes estándar de respuesta, no plantillas utility |
| `Marketing API Access Tier` | No gestionan campañas vía API todavía |

**Permisos mínimos viables** para el agente IG actual:  
`instagram_business_basic`, `instagram_business_manage_messages`, `pages_show_list`, `pages_manage_metadata`, `pages_messaging`, `business_management`, `public_profile`, `Human Agent` (+ `instagram_basic` / `instagram_manage_messages` si Meta los exige en el bundle).

---

## Checklist antes de enviar

- [ ] App en modo **Live** con al menos un admin verificado  
- [ ] Política de privacidad publicada (URL en configuración de la app)  
- [ ] Llamadas de prueba API completadas (WhatsApp, Pages, Ads donde aplique)  
- [ ] Video subido por cada permiso que lo exige  
- [ ] Checkbox «Confirmo uso permitido» marcado en cada permiso  
- [ ] Dependencias respetadas (`instagram_business_basic` antes de `manage_messages`, etc.)  
- [ ] Permisos no implementados eliminados de la solicitud  

---

*Documento generado para Tecbite Panamá — revisión Meta App Review 2026.*  
*Contacto técnico: [completar email del desarrollador/administrador de la app]*
