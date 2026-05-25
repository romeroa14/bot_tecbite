import { workflow, node, trigger, newCredential } from '@n8n/workflow-sdk';

const SYSPROMPT = 'Eres el asesor virtual de Tecbite Panamá, especialista en accesorios Thule y WeatherTech. Respondes por Instagram DM en español de Panamá, con tono claro, rápido y amable.\\n\\n## REGLA INVIOLABLE — SOLO DATOS DE TOOLS\\nTu conocimiento de productos está DESACTUALIZADO.\\n- SOLO puedes mencionar productos que aparezcan LITERALMENTE en resultados de tools.\\n- NUNCA inventes SKU, precio, stock, compatibilidad ni modelos.\\n- NUNCA uses conocimiento previo de Thule/WeatherTech/CURT.\\n\\n## ALCANCE DE MARCA (OBLIGATORIO)\\n- Solo recomienda Thule y WeatherTech.\\n- No recomiendes otras marcas.\\n- Barras/kits/canasta/baúl/portabici => Thule.\\n- Alfombras/floorliner/cargo liner => WeatherTech.\\n\\n## FLUJO GUIADO OBLIGATORIO (SLOT FILLING)\\nAntes de buscar productos finales, completa estos slots:\\n1) intención/categoría\\n2) marca del vehículo\\n3) modelo del vehículo\\n4) año del vehículo\\n5) tipo de techo (OBLIGATORIO para barras/roof rack/canasta/baúl)\\n\\nReglas duras:\\n- Si falta cualquier slot, NO llames tools de catálogo todavía.\\n- Haz UNA sola pregunta concreta por turno para completar el siguiente slot faltante.\\n- NO asumas año/modelo/marca del historial si el mensaje actual no lo confirma.\\n- Ejemplo: si el usuario dice \\"barras para yaris\\" y no dice año, debes preguntar el año antes de buscar.\\n\\nOrden recomendado de preguntas:\\n1) marca/modelo/año (si faltan)\\n2) tipo de techo (si aplica barras)\\n3) búsqueda de productos\\n\\n## GATE OBLIGATORIO — BARRAS / ROOF RACK\\nSi la intención es barras, kit, canasta o baúl y falta tipo de techo:\\n- NO des recomendación final.\\n- NO llames tools todavía.\\n- Responde con guía breve y agrega exactamente: [ROOF_MENU]\\n- El sistema enviará imagen + botones A/B/C/D/E automáticamente.\\n\\nInterpretación de selección:\\n- QR:ROOF_A o \\"A\\" => Riel elevado\\n- QR:ROOF_B o \\"B\\" => Riel alineado\\n- QR:ROOF_C o \\"C\\" => Punto de fijación\\n- QR:ROOF_D o \\"D\\" => Techo liso\\n- QR:ROOF_E o \\"E\\" => Canal de agua\\n\\nDespués de seleccionar techo:\\n1) confirma el tipo elegido\\n2) confirma marca/modelo/año (si falta alguno, pregúntalo)\\n3) recién ahí llama tools y recomienda opciones\\n\\n## FLUJOS GUIADOS POR CATEGORÍA (SIMILAR A MANYCHAT)\\n### THULE — menú principal\\nSi el usuario pide cotización general Thule y no especifica producto:\\n- Pregunta qué busca: Barras, Canasta/Baúl, Plataforma, Portabicicleta, Tienda/Tolda, Repuestos.\\n\\n### Portabicicletas (Thule)\\nAntes de recomendar:\\n1) tipo de montaje (Techo, Maletero, Pick-up, Bola, Hitch, Accesorios)\\n2) tipo de bicicleta (Ruta, MTB, Eléctrica)\\nValidaciones:\\n- Techo => confirmar si tiene barras instaladas; si NO, redirigir a flujo de barras.\\n- Hitch => confirmar si tiene sistema de remolque; si NO, escalar a asesor.\\n- Eléctrica => solo opciones compatibles según catálogo/tool (no inventar).\\n\\n### WeatherTech\\nAntes de recomendar:\\n1) marca/modelo/año (obligatorio)\\n2) tipo: alfombra por fila vs universal\\n3) luego buscar y mostrar opciones con selección guiada.\\n\\n## CUÁNDO LLAMAR CADA TOOL\\n- decode_ad_ref: SIEMPRE que llegue ad_ref.\\n- search_attributes_jsonb: SOLO cuando slots mínimos estén completos.\\n  - Usar brand_filter=\\"Thule\\" para barras/kits/canasta/baúl/portabici.\\n  - Usar brand_filter=\\"WeatherTech\\" para alfombras/floorliner.\\n- search_vehicle_fitment: fallback cuando search_attributes_jsonb no encuentre.\\n- search_products_by_brand: detalle por SKU (especialmente QR:SELECT_N).\\n- vector_search_docs: SOLO para preguntas técnicas ya concretas (instalación en detalle, resistencia/carga específica, compatibilidad con un caso puntual, e-bike, etc.). Si el usuario solo dice \\"más información\\" / \\"más info\\" dentro de tema de producto ya activo, primero aclara QUÉ detalle sin llamar tools.\\n\\nSecuencia correcta:\\n1) completar slots\\n2) search_attributes_jsonb\\n3) si found=false => search_vehicle_fitment\\n4) responder con opciones guiadas (2-3) si hay resultados\\n\\n## POLÍTICA DE SIN RESULTADOS (OBLIGATORIA)\\nCuando una tool devuelva found=false o count=0:\\n\\nPASO 1 — Revisar slots:\\n- Si falta algún slot, pregunta por ese dato.\\n- Prohibido decir \\"no hay\\" ni escalar a WhatsApp en este paso.\\n\\nPASO 2 — Fallback técnico (solo con slots completos):\\n- Ejecuta el segundo intento (search_vehicle_fitment o búsqueda menos restrictiva manteniendo marca permitida).\\n- No inventes resultados.\\n\\nPASO 3 — Escalamiento (solo después de 2 intentos fallidos):\\n- Explica que no hay match exacto en sistema para esa combinación.\\n- Ofrece WhatsApp (Dave y Eduardo).\\n- Cierra con pregunta de continuidad (otra categoría, opción universal, etc.).\\n\\nProhibido:\\n- Responder solo \\"no hay\\".\\n- Escalar a WhatsApp en el primer fallo.\\n- Buscar catálogo sin año confirmado.\\n\\n## FORMATO DE IMÁGENES\\nCuando las tools devuelvan image_url, incluye:\\n[IMG:https://url-de-la-imagen.jpg]\\n *Título exacto* — $precio (stock)\\n\\nPara techo, NO pegues URLs manualmente: usa [ROOF_MENU] y el sistema envía imágenes persistidas.\\n\\n## SIN STOCK / DESCONTINUADO\\nSi stock es out_of_stock o discontinued:\\n- SÍ mostrar producto si es relevante.\\n- SÍ incluir [IMG:url] y precio literal.\\n- Aclarar que no hay inventario actual.\\n- Ofrecer WhatsApp:\\n  - Dave: https://api.whatsapp.com/send?phone=50769880471&text=Hola%20Dave%2C%20buen%20d%C3%ADa.%0ATe%20contacto%20de%20Tecbite%20porque%20estoy%20interesado%20en%20algunos%20productos%20Thule%20y%20WeatherTech%20y%20quisiera%20recibir%20tu%20asesor%C3%ADa.\\n  - Eduardo: https://api.whatsapp.com/send?phone=50769504792&text=Hola%20Eduardo%2C%20buen%20d%C3%ADa.%0ATe%20escribo%20porque%20necesito%20tu%20asistencia%20con%20unos%20productos%20Thule%20y%20WeatherTech.%20%C2%BFMe%20puedes%20orientar%20por%20favor%3F\\n\\n## QUICK REPLIES\\nCuando recomiendes 2+ productos, el sistema agrega botones 1️⃣ 2️⃣ 3️⃣ 📞 WhatsApp.\\n\\nInterpretación:\\n- QR:SELECT_0/1/2 => producto elegido de la última recomendación\\n- QR:WHATSAPP => usuario quiere asesor humano\\n\\nSi recibes QR:SELECT_N:\\n- Busca ese SKU con search_products_by_brand y responde detalle.\\n\\nSi recibes QR:WHATSAPP:\\n- Responde con ambos enlaces de WhatsApp (Dave y Eduardo).\\n\\n## ESTILO DE RESPUESTA\\n- Máximo 4 párrafos cortos.\\n- Una pregunta concreta por turno cuando falten datos.\\n- Si hay 2-3 opciones válidas, presenta todas y pide elección (no cierres con una sola opción).\\n- Solo SKUs/precios literales de tools.\\n- Si hay promo: \\"🔥 *PROMO*: ...\\"\\n- Cierra con pregunta breve de seguimiento.\\n\\n## MEMORIA Y CONTINUIDAD CONTEXTUAL (OBLIGATORIO)\\n- Usas Window Memory para el hilo ACTUAL (mensajes recientes usuario/asistente). Distingue: (A) menú esperando ELECCIÓN de categoría vs (B) conversación ya enfocada en producto/categoría/vehículo.\\n- Caso A: si TU último turno fue menú cotización tipo \\"¿Qué deseas cotizar?\\"/lista de categorías o pediste elegir opción principal y el usuario solo escribe genérico sin elegir (necesito más información, más información, más info, quiero información, info, sin mencionar barras/canasta/portabici/WeatherTech/etc.): NO infieras categoría ni año/modelo desde contexto viejo del hilo; repite invitación a elegir categoría y agrega exactamente: [MAIN_MENU].\\n- Caso B: si últimos turnos ya son sustanciales sobre producto/categoría/vehículo (ej. barras Thule LC250 canal de agua, WeatherTech Corolla Cross, opciones cotizadas): seguimiento genérico igual => mantén el tema. Una frase de continuidad (\\"Seguimos con …\\") y pregunta qué detalle prioriza: instalación, compatibilidad, precio/stock/promos, otros accesorios o asesor/WhatsApp. Sin [MAIN_MENU]. Sin llamar tools en ese mismo turno salvo que el usuario ya aclaró un detalle que exija búsqueda/docs o slots ya completos para catálogo.\\n- Reinicio explícito: menciones de \\"menú\\", \\"menu\\", \\"inicio\\", \\"empezar de nuevo\\", \\"empezar de cero\\", \\"otra cotización\\", \\"nueva cotización\\", \\"cambiar de tema\\", \\"quiero cotizar otra cosa\\" => corta tema previo cortésmente y agrega exactamente: [MAIN_MENU].\\n\\n## MARCADORES DE MENÚ (OBLIGATORIO)\\n- Saludo inicial sin categoría definida o conversación recién iniciada fuera de flujo específico: breve bienvenida y exactamente [MAIN_MENU]. NO uses [MAIN_MENU] solo por \\"más información\\" si aplica MEMORIA Caso B (conversación de producto activa).\\n- Usuario pide alfombras/floorliner y falta tipo => agrega exactamente: [WT_MENU]\\n- Usuario pide barras/roof rack y falta tipo de techo => agrega exactamente: [ROOF_MENU]\\n- Con [MAIN_MENU], [WT_MENU] o [ROOF_MENU] NO pidas otros datos en el mismo turno.\\n- Después de QR:CAT_BARS => pedir solo marca/modelo/año, luego [ROOF_MENU].\\n- Después de QR:CAT_WT => pedir solo marca/modelo/año, luego [WT_MENU].\\n- Después de QR:WT_ROW o QR:WT_UNIV => buscar con tools.\\n- Nunca pidas confirmación extra (\\"¿correcto?\\"). Avanza al siguiente slot.\\n- Cuando listes 2-3 productos usa formato 1️⃣ 2️⃣ 3️⃣ para activar botones.\\n';

const webhookGet = trigger({ type:'n8n-nodes-base.webhook', version:1, config:{ name:'Instagram Webhook GET2', parameters:{ path:'instagram-webhook-v2', options:{} }, position:[0,0] }, output:[{ query:{'hub.mode':'subscribe'} }] });
const verifyGet = node({ type:'n8n-nodes-base.code', version:2, config:{ name:'Verify GET2', parameters:{ jsCode:"const q=$json.query||{};if(q['hub.mode']==='subscribe'&&q['hub.verify_token']==='instagram-webhook'){return [{json:{challenge:q['hub.challenge']}}];}return [{json:{error:'invalid token'}}];" }, position:[224,0] }, output:[{challenge:'123'}] });
const webhookPost = trigger({ type:'n8n-nodes-base.webhook', version:1, config:{ name:'Instagram Webhook POST2', parameters:{ httpMethod:'POST', path:'instagram-webhook', options:{} }, position:[0,336] }, output:[{body:{entry:[{messaging:[{message:{text:'hola'}}]}]}}] });

const filterNorm = node({ type:'n8n-nodes-base.code', version:2, config:{ name:'Filter & Normalize2', parameters:{ jsCode:`const body=$json.body||{};const entry=body.entry?.[0]||{};const messaging=entry.messaging?.[0]||{};const message=messaging.message||{};if(message.is_echo===true)return[];const senderId=String(messaging.sender?.id||'').trim();const pageId=String(entry.id||'').trim();if(senderId&&pageId&&senderId===pageId)return[];if(!messaging.message)return[];const quickReplyPayload=String(message.quick_reply?.payload||'').trim();const text=String(message.text||'').trim();let messageText=text;const foldInbound=(v)=>String(v||'').toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g,'');if(quickReplyPayload){messageText='QR:'+quickReplyPayload;}else{const f=foldInbound(text);let mapped='';if(/\\bbarras?\\b/.test(f)||/\\broof\\s*racks?\\b/.test(f))mapped='QR:CAT_BARS';else if(/\\bcargo\\s+liner\\b/.test(f)||/\\bfloor\\s*liner\\b/.test(f)||/\\balfombras?\\b/.test(f)||/\\bweathertech\\b/.test(f))mapped='QR:CAT_WT';else if(/\\bcanasta\\b/.test(f)||/\\bbaul(es)?\\b/.test(f)||/\\bcargo\\b/.test(f))mapped='QR:CAT_CARGO';else if(/\\b(?:portabicicleta|portabici|bici)\\b/.test(f))mapped='QR:CAT_BIKE';else if(/\\bpor\\s+fila\\b/.test(f)||/\\bfila\\b/.test(f)||/\\bdelanteras?\\b/.test(f)||/\\btraseras?\\b/.test(f))mapped='QR:WT_ROW';else if(/\\buniversal\\b/.test(f))mapped='QR:WT_UNIV';else if(/\\bwhatsapp\\b/.test(f)||/\\basesor\\b/.test(f)||/\\bhumano\\b/.test(f))mapped='QR:WHATSAPP';if(mapped){messageText=mapped;}else if(/^[1-3]$/.test(text)){messageText='QR:SELECT_'+(Number(text)-1);}else if(/^[A-E]$/i.test(text)){messageText='QR:ROOF_'+text.toUpperCase();}else{const roofInText=text.match(/(?:opci[oó]n|tipo(?:\\s+de\\s+techo)?)\\s*([A-E])\\b/i);if(roofInText)messageText=text+'\\n[USER_ROOF:'+roofInText[1].toUpperCase()+']';}}if(!messageText)return[];const messageId=String(message.mid || 'msg_' + Date.now() + '_' + Math.random().toString(36).substring(2, 7)).trim();const referral=messaging.referral||{};return[{json:{user_id:senderId||null,message_text:messageText,ad_ref:String(referral.ref||'').trim(),ad_id:String(referral.ad_id||'').trim(),ad_source:String(referral.source||'').trim(),ad_title:String(referral.ad_title||'').trim(),session_key:senderId||'anon',message_id:messageId}}];` }, position:[224,336] }, output:[{user_id:'123',message_text:'hola',session_key:'123',message_id:'abc'}] });

const getLeadState = node({
  type: 'n8n-nodes-base.postgres',
  version: 2.5,
  config: {
    name: 'Get Lead State',
    parameters: {
      operation: 'executeQuery',
      query: `SELECT 
  COALESCE(s.conversation_id, $1) as conversation_id,
  COALESCE(s.user_id, $1) as user_id,
  COALESCE(s.channel, 'instagram') as channel,
  COALESCE(s.stage, 'greeting') as stage,
  s.make,
  s.model,
  s.year,
  s.category,
  COALESCE(s.slots_complete, false) as slots_complete,
  s.last_message_id
FROM (SELECT $1 AS dummy_id) d
LEFT JOIN instagram_conversation_state s ON s.conversation_id = d.dummy_id;`,
      options: {
        queryReplacement: '={{ $json.user_id }}'
      }
    },
    credentials: {
      postgres: {
        name: 'Tecbite Postgres'
      }
    },
    position: [380, 336]
  }
});

const openRouterModel = node({ type:'@n8n/n8n-nodes-langchain.lmChatOpenRouter', version:1, config:{ name:'OpenRouter Chat Model', parameters:{ options:{} }, position:[448,560] } });

const windowMemory = node({ type:'@n8n/n8n-nodes-langchain.memoryBufferWindow', version:1.3, config:{ name:'Window Memory2', parameters:{ sessionIdType:'customKey', sessionKey:"={{ $('Filter & Normalize2').item.json.session_key }}", contextWindowLength:12 }, position:[576,560] } });

const toolDecodeAd = node({ type:'@n8n/n8n-nodes-langchain.toolWorkflow', version:1.3, config:{ name:'Tool: decode_ad_ref2', parameters:{ name:'decode_ad_ref', description:'Decodifica ad_ref del anuncio Instagram. Input: { "ad_ref": "string" }', workflowId:{ __rl:true, value:'0gaRaUaSu2BzrV03', mode:'list' }, specifyInputSchema:true, schemaType:'manual', inputSchema:'{"type":"object","properties":{"ad_ref":{"type":"string"}},"required":["ad_ref"]}' }, position:[704,560] } });

const toolFitment = node({ type:'@n8n/n8n-nodes-langchain.toolWorkflow', version:1.3, config:{ name:'Tool: search_vehicle_fitment2', parameters:{ name:'search_vehicle_fitment', description:'Busca productos compatibles con vehículo en vehicles + vehicle_product_fitment. Input: { "brand", "model", "year" }', workflowId:{ __rl:true, value:'uuZdDhhevVTeBgDd', mode:'list' }, specifyInputSchema:true, schemaType:'manual', inputSchema:'{"type":"object","properties":{"brand":{"type":"string"},"model":{"type":"string"},"year":{"type":"integer"}},"required":["brand","model","year"]}' }, position:[832,560] } });

const toolAttributes = node({ type:'@n8n/n8n-nodes-langchain.toolWorkflow', version:1.3, config:{ name:'Tool: search_attributes_jsonb2', parameters:{ name:'search_attributes_jsonb', description:'Busca productos en tecbite_product_state por attributes JSONB. Input: { "brand", "model"?, "year"?, "brand_filter"?, "product_hint"? }', workflowId:{ __rl:true, value:'C3Mx8TtH3ABEv178', mode:'list' }, specifyInputSchema:true, schemaType:'manual', inputSchema:'{"type":"object","properties":{"brand":{"type":"string"},"model":{"type":"string"},"year":{"type":"integer"},"brand_filter":{"type":"string"},"product_hint":{"type":"string"}},"required":["brand"]}' }, position:[960,560] } });

const toolBrand = node({ type:'@n8n/n8n-nodes-langchain.toolWorkflow', version:1.3, config:{ name:'Tool: search_products_by_brand2', parameters:{ name:'search_products_by_brand', description:'Lista productos activos de una marca (Thule, WeatherTech, CURT). Input: { "brand", "category"?, "limit"? }', workflowId:{ __rl:true, value:'RheRa72JDJql6QkU', mode:'list' }, specifyInputSchema:true, schemaType:'manual', inputSchema:'{"type":"object","properties":{"brand":{"type":"string"},"category":{"type":"string"},"limit":{"type":"integer"}},"required":["brand"]}' }, position:[1088,560] } });

const toolVector = node({ type:'@n8n/n8n-nodes-langchain.toolWorkflow', version:1.3, config:{ name:'Tool: vector_search_docs2', parameters:{ name:'vector_search_docs', description:'Búsqueda semántica en docs Thule/WeatherTech (pgvector). Input: { "query", "top_k"?, "vendor"? }', workflowId:{ __rl:true, value:'nMBKUH7Pb6CVX7WX', mode:'list' }, specifyInputSchema:true, schemaType:'manual', inputSchema:'{"type":"object","properties":{"query":{"type":"string"},"top_k":{"type":"integer"},"vendor":{"type":"string"}},"required":["query"]}' }, position:[1216,560] } });

const aiAgent = node({
  type: '@n8n/n8n-nodes-langchain.agent',
  version: 1.7,
  config: {
    name: 'AI Agent',
    parameters: {
      promptType: 'define',
      text: "={{ $('Filter & Normalize2').item.json.message_text }}{{ $('Filter & Normalize2').item.json.ad_ref ? '\\n\\n[CONTEXTO DEL ANUNCIO]\\nad_ref: ' + $('Filter & Normalize2').item.json.ad_ref + ($('Filter & Normalize2').item.json.ad_id ? '\\nad_id: ' + $('Filter & Normalize2').item.json.ad_id : '') : '' }}{{ $('Filter & Normalize2').item.json.ad_title ? '\\n\\n[TÍTULO DEL ANUNCIO]\\n' + $('Filter & Normalize2').item.json.ad_title : '' }}\\n\\n[ESTADO CONVERSACIONAL EN BD]\\n- marca (make): {{ $json.make || 'no definido' }}\\n- modelo (model): {{ $json.model || 'no definido' }}\\n- año (year): {{ $json.year || 'no definido' }}\\n- categoria (category): {{ $json.category || 'no definido' }}\\n- stage_actual: {{ $json.stage || 'greeting' }}",
      options: {
        systemMessage: SYSPROMPT,
        maxIterations: 5,
        returnIntermediateSteps: true
      }
    },
    subnodes: {
      model: openRouterModel,
      memory: windowMemory,
      tools: [toolDecodeAd, toolFitment, toolAttributes, toolBrand, toolVector]
    },
    position: [768, 336]
  },
  output: [{ output: 'text', intermediateSteps: [] }]
});

const parseStateUpdates = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Parse State Updates',
    parameters: {
      jsCode: `const agentOutput = $input.first().json;
const steps = Array.isArray(agentOutput.intermediateSteps) ? agentOutput.intermediateSteps : [];

let prevMake = null;
let prevModel = null;
let prevYear = null;
let prevCategory = null;
let prevStage = 'greeting';
try {
  const prevState = $('Get Lead State').item.json;
  prevMake = prevState.make;
  prevModel = prevState.model;
  prevYear = prevState.year;
  prevCategory = prevState.category;
  prevStage = prevState.stage;
} catch (_) {}

let make = prevMake;
let model = prevModel;
let year = prevYear;
let category = prevCategory;

for (const step of steps) {
  const toolInput = step?.action;
  if (toolInput) {
    if (toolInput.brand && !make) make = toolInput.brand;
    if (toolInput.brand_filter && !make) make = toolInput.brand_filter;
    if (toolInput.model && !model) model = toolInput.model;
    if (toolInput.year && !year) year = Number(toolInput.year);
    if (toolInput.category && !category) category = toolInput.category;
  }
}

let inboundText = '';
let outboundText = agentOutput.output || agentOutput.text || '';
try {
  inboundText = String($('Filter & Normalize2').item.json.message_text || '').trim();
} catch (_) {}

const textToScan = (inboundText + ' ' + outboundText).toLowerCase();
if (!category) {
  if (textToScan.includes('barra') || textToScan.includes('roof rack') || textToScan.includes('portaequipaje')) {
    category = 'Barras techo';
  } else if (textToScan.includes('alfombra') || textToScan.includes('floorliner') || textToScan.includes('weathertech')) {
    category = 'Alfombras WT';
  } else if (textToScan.includes('canasta') || textToScan.includes('baul') || textToScan.includes('baúl')) {
    category = 'Canasta/Baúl';
  } else if (textToScan.includes('portabici') || textToScan.includes('bici')) {
    category = 'Portabici';
  }
}

let stage = prevStage;
const outputUpper = outboundText.toUpperCase();
if (outputUpper.includes('[ROOF_MENU]')) {
  stage = 'collect_category';
} else if (outputUpper.includes('[WT_MENU]')) {
  stage = 'collect_category';
} else if (outputUpper.includes('[MAIN_MENU]')) {
  stage = 'collect_category';
} else if (outboundText.includes('Dave') || outboundText.includes('Eduardo') || outboundText.includes('WhatsApp') || outputUpper.includes('WHATSAPP')) {
  stage = 'handoff';
} else {
  if (!category) stage = 'collect_category';
  else if (!make) stage = 'collect_make';
  else if (!model) stage = 'collect_model';
  else if (!year) stage = 'collect_year';
  else stage = 'recommend';
}

const slots_complete = !!(make && model && year && category);

let user_id = '';
let message_id = '';
try {
  user_id = $('Filter & Normalize2').item.json.user_id || '';
  message_id = $('Filter & Normalize2').item.json.message_id || '';
} catch (_) {}

return [{
  json: {
    conversation_id: user_id,
    user_id: user_id,
    make: make ? String(make).trim() : null,
    model: model ? String(model).trim() : null,
    year: year ? Number(year) : null,
    category: category ? String(category).trim() : null,
    stage: stage,
    slots_complete: slots_complete,
    message_id: message_id,
    inbound_payload: { text: inboundText },
    outbound_payload: { text: outboundText }
  }
}];`
    },
    position: [960, 180]
  }
});

const saveLeadState = node({
  type: 'n8n-nodes-base.postgres',
  version: 2.5,
  config: {
    name: 'Save Lead State',
    parameters: {
      operation: 'executeQuery',
      query: `INSERT INTO instagram_conversation_state (
  conversation_id, user_id, channel, stage, make, model, year, category, slots_complete, last_message_id, updated_at
) VALUES (
  $1, $2, 'instagram', $3, NULLIF($4, 'null'), NULLIF($5, 'null'), NULLIF($6, 'null')::integer, NULLIF($7, 'null'), $8, $9, NOW()
)
ON CONFLICT (conversation_id) DO UPDATE SET
  stage = EXCLUDED.stage,
  make = COALESCE(EXCLUDED.make, instagram_conversation_state.make),
  model = COALESCE(EXCLUDED.model, instagram_conversation_state.model),
  year = COALESCE(EXCLUDED.year, instagram_conversation_state.year),
  category = COALESCE(EXCLUDED.category, instagram_conversation_state.category),
  slots_complete = EXCLUDED.slots_complete,
  last_message_id = EXCLUDED.last_message_id,
  updated_at = NOW();

INSERT INTO instagram_conversation_event (
  conversation_id, message_id, event_type, payload, created_at
) VALUES (
  $1, $9, 'inbound', $10::jsonb, NOW()
)
ON CONFLICT (conversation_id, message_id, event_type) DO NOTHING;

INSERT INTO instagram_conversation_event (
  conversation_id, message_id, event_type, payload, created_at
) VALUES (
  $1, $9, 'recommendation', $11::jsonb, NOW()
)
ON CONFLICT (conversation_id, message_id, event_type) DO NOTHING;`,
      options: {
        queryReplacement: '={{ $json.conversation_id }},={{ $json.user_id }},={{ $json.stage }},={{ $json.make }},={{ $json.model }},={{ $json.year }},={{ $json.category }},={{ $json.slots_complete }},={{ $json.message_id }},={{ JSON.stringify($json.inbound_payload) }},={{ JSON.stringify($json.outbound_payload) }}'
      }
    },
    credentials: {
      postgres: {
        name: 'Tecbite Postgres'
      }
    },
    position: [1120, 180]
  }
});

const FORMAT_CODE = `const agentOutput=$input.first().json;const outputText=agentOutput.output||agentOutput.text||'';let user_id='';let inboundText='';try{user_id=$('Filter & Normalize2').item.json.user_id||'';}catch(_){}try{inboundText=String($('Filter & Normalize2').item.json.message_text||'').trim();}catch(_){}const fold=(v)=>String(v||'').toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g,'');const outbound=fold(outputText);const inboundFold=fold(inboundText.replace(/^qr:/i,''));const explicitRoof=outputText.includes('[ROOF_MENU]');const explicitMain=outputText.includes('[MAIN_MENU]');const explicitWt=outputText.includes('[WT_MENU]');const roofCtx=/\\b(barras?|roof\\s*racks?|portaequipajes?|portabici|canasta|ba[uú]l)\\b/i.test(outputText+' '+inboundFold);const wtCtx=/\\b(alfombras?|floor\\s*liners?|cargo\\s+liners?|weathertech)\\b/i.test(outputText+' '+inboundFold);const roofCue=/\\btipo\\s+de\\s+techo\\b/i.test(outputText)||/\\bOpci[oó]n\\s+[A-E]\\b/i.test(outputText);const wtCue=/\\b(fila|filas|universal|FloorLiner)\\b/i.test(outputText)&&/\\b(tipo|cu[aá]l)\\b/i.test(outputText);const mainCue=/\\b(qu[eé]|que)\\s+(deseas|tipo)\\b/i.test(outbound)||[/barras?/i,/portabic/i,/alfombras?/i,/canasta|ba[uú]l/i].filter(r=>r.test(outputText)).length>=2;const askV=/\\b(marca|modelo|año)\\b/i.test(outputText)&&/\\b(cu[aá]l|indic|dime|necesito)\\b/i.test(outbound);let roofMenu=explicitRoof||(!explicitWt&&!explicitMain&&roofCtx&&roofCue&&!askV);let wtMenu=explicitWt||(!explicitRoof&&!explicitMain&&wtCtx&&wtCue&&!askV);let mainMenu=explicitMain||(!explicitRoof&&!explicitWt&&mainCue&&!askV);if(roofMenu&&wtMenu)wtMenu=false;if(roofMenu&&mainMenu)mainMenu=false;if(wtMenu&&mainMenu)mainMenu=false;const ROOF_IMAGES={MENU:'https://drive.google.com/uc?export=view&id=1ett4opof8jzK9APUJtF71kXnEBwYYs-4',ROOF_A:'https://drive.google.com/uc?export=view&id=1f7d0gXJ-PLWxUQ-yRxjlqRlAogqToDOR',ROOF_B:'https://drive.google.com/uc?export=view&id=15KVOsDgmM9DQw1vSDxY7bIuXaBl7i_WK',ROOF_C:'https://drive.google.com/uc?export=view&id=1cFLKfJeqTKIx1hiC6lUFQzBCWyfUopp6',ROOF_D:'https://drive.google.com/uc?export=view&id=1vbRJIfryNZr0TEPzrvml9LWhJ0k0DGMJ',ROOF_E:'https://drive.google.com/uc?export=view&id=17n_ATH7WaqC7UXu3jI0owKDRF-0gDlDT'};const normRoof=(v)=>{const r=String(v||'').trim().toUpperCase();if(r.startsWith('QR:ROOF_'))return r.replace('QR:','');if(r.startsWith('ROOF_'))return r;if(/^[A-E]$/.test(r))return'ROOF_'+r;const m=r.match(/\\[USER_ROOF:([A-E])\\]/);return m?'ROOF_'+m[1]:''};const selRoof=normRoof(inboundText);const imageUrls=[];const seen=new Set();const pushUrl=(u)=>{if(typeof u==='string'&&/^https?:\\/\\//i.test(u.trim())&&!seen.has(u.trim())){seen.add(u.trim());imageUrls.push(u.trim());}};if(roofMenu)pushUrl(ROOF_IMAGES.MENU);if(selRoof&&ROOF_IMAGES[selRoof])pushUrl(ROOF_IMAGES[selRoof]);const steps=Array.isArray(agentOutput.intermediateSteps)?agentOutput.intermediateSteps:[];for(const step of steps){let data=step?.observation;if(typeof data==='string'){try{data=JSON.parse(data);}catch(_){data=null;}}const results=Array.isArray(data?.results)?data.results:[];for(const row of results){const brand=String(row?.brand||'').toLowerCase();if(brand&&!brand.includes('thule')&&!brand.includes('weathertech'))continue;pushUrl(row?.image_url);}}const imgPat=/\\[IMG:(https?:\\/\\/[^\\]\\s]+)\\]/g;let match;while((match=imgPat.exec(outputText))!==null)pushUrl(match[1]);let cleanText=outputText.replace(/\\[IMG:https?:\\/\\/[^\\]\\s]+\\]/g,'').replace(/\\[(ROOF_MENU|MAIN_MENU|WT_MENU)\\]/g,'').replace(/\\n{3,}/g,'\\n\\n').trim();const countProducts=(t)=>{const e=t.match(/\\d+️⃣/g)||[];if(e.length>=2)return Math.min(e.length,3);const l=t.split('\\n').filter(l=>/^\\s*(\\d+[.)\\]]|🔹|\\d+️⃣)/.test(l.trim()));return l.length>=2?Math.min(l.length,3):0;};const prodOpts=countProducts(outputText);let qrConfig=null;if(roofMenu){qrConfig={options:['A Riel elev.','B Riel alin.','C Punto fij.','D Techo liso','E Canal agua'],payloads:['ROOF_A','ROOF_B','ROOF_C','ROOF_D','ROOF_E']};if(!cleanText||cleanText.length<10)cleanText='Elige el tipo de techo de tu vehículo:';}else if(mainMenu){qrConfig={options:['Barras techo','Canasta/Baúl','Portabici','Alfombras WT','WhatsApp'],payloads:['CAT_BARS','CAT_CARGO','CAT_BIKE','CAT_WT','WHATSAPP']};if(!cleanText||cleanText.length<10)cleanText='¡Hola! 👋 ¿Qué deseas cotizar?';}else if(wtMenu){qrConfig={options:['Por fila','Universal','WhatsApp'],payloads:['WT_ROW','WT_UNIV','WHATSAPP']};if(!cleanText||cleanText.length<10)cleanText='¿Qué tipo de alfombra buscas?';}else if(prodOpts>=2){const opts=[];const pays=[];for(let i=0;i<prodOpts;i++){opts.push((i+1)+'️⃣');pays.push('SELECT_'+i);}opts.push('📞 WhatsApp');pays.push('WHATSAPP');qrConfig={options:opts,payloads:pays};}const messages=[];if(qrConfig){messages.push({type:'text_with_quick_replies',content:(cleanText||'¡Hola!').substring(0,2000),options:qrConfig.options,payloads:qrConfig.payloads,user_id});}else{const maxImg=Math.min(imageUrls.length,5);for(let i=0;i<maxImg;i++){messages.push({type:'image',image_url:imageUrls[i],user_id});}if(cleanText){messages.push({type:'text',content:cleanText.substring(0,2000),user_id});}}if(messages.length===0)messages.push({type:'text',content:'¡Hola! ¿Cómo puedo ayudarte?',user_id});return messages.map(m=>({json:m}));`;

const formatMsg = node({ type:'n8n-nodes-base.code', version:2, config:{ name:'Format Instagram Messages2', parameters:{ jsCode: FORMAT_CODE }, position:[1424,336] }, output:[{type:'text_with_quick_replies',content:'¿Qué deseas cotizar?',options:['Barras'],payloads:['CAT_BARS'],user_id:'123'}] });

const BUILD_CODE = `const items=$input.all();const fallbackUserId=(()=>{try{return $('Filter & Normalize2').item.json.user_id;}catch(_){return'';}})();return items.map((item)=>{const msg=item.json||{};const userId=msg.user_id||fallbackUserId;const recipient={id:userId};let body;if(msg.type==='image'&&msg.image_url){body=JSON.stringify({recipient,message:{attachment:{type:'image',payload:{url:msg.image_url,is_reusable:true}}}});}else if(msg.type==='text_with_quick_replies'&&msg.options&&msg.options.length>0){const qr=[];const max=Math.min(msg.options.length,13);for(let i=0;i<max;i++){qr.push({content_type:'text',title:String(msg.options[i]).substring(0,20),payload:(msg.payloads&&msg.payloads[i])?String(msg.payloads[i]).substring(0,1000):'OPTION_'+i});}body=JSON.stringify({recipient,message:{text:String(msg.content||'Elige:').substring(0,2000),quick_replies:qr}});}else{body=JSON.stringify({recipient,message:{text:String(msg.content||msg.text||'¡Hola!').substring(0,1000)}});}return{json:{body,user_id:userId,message_type:msg.type||'text'}};});`;

const buildReq = node({ type:'n8n-nodes-base.code', version:2, config:{ name:'Build Instagram Request', parameters:{ jsCode: BUILD_CODE }, position:[1648,336] }, output:[{body:'{}',user_id:'123',message_type:'text'}] });

const igSend = node({ type:'n8n-nodes-base.httpRequest', version:4.2, config:{ name:'Instagram Send2', parameters:{ method:'POST', url:'https://graph.facebook.com/v21.0/me/messages', sendQuery:true, queryParameters:{ parameters:[{ name:'access_token', value:'EAF0f2bD8sbsBRYMfa0ZB6ULsaZAVKBYuHmrSPeOVCx3VP7V1Wq6JOnUFuMj5bTunxsYCl6i6muTNo6lHOskSMR0NwiKJZBmN0bP5JYlT5HnX5pwj1dZCQhOUzaZBmlisZASZCZBiSVYnyUXvkR9yXXML4R0we7YhGFQEy0OFD4y8ZB2nEDqegvB9xZAHZBZA9rEQZCuIyakFgkN3bSZAWSMkSfZBRM8' }] }, sendHeaders:true, headerParameters:{ parameters:[{ name:'Content-Type', value:'application/json' }] }, sendBody:true, contentType:'raw', rawContentType:'application/json', body:'={{ $json.body }}', options:{ response:{ response:{ neverError:true } } } }, position:[1872,336] }, output:[{recipient_id:'123',message_id:'abc'}] });

export default workflow('oYVEXFvUFdCoe9VG', 'Tecbite AI Agent v2 - Tools Agent (OpenRouter + DeepSeek)')
  .add(webhookGet).to(verifyGet)
  .add(webhookPost).to(filterNorm).to(getLeadState).to(aiAgent)
  .add(aiAgent).to(formatMsg).to(buildReq).to(igSend)
  .add(aiAgent).to(parseStateUpdates).to(saveLeadState);
