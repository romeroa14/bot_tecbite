// Shared sales advisor config for Instagram handoff flows.
const SALES_ADVISORS = [
  {
    id: 'DAVE',
    name: 'Dave',
    qrLabel: 'Dave',
    qrPayload: 'ADV_DAVE',
    phone: '50769880471',
    waText: 'Hola Dave, buen día. Te contacto de Tecbite porque estoy interesado en algunos productos Thule y WeatherTech y quisiera recibir tu asesoría.',
  },
  {
    id: 'EDUARDO',
    name: 'Eduardo',
    qrLabel: 'Eduardo',
    qrPayload: 'ADV_EDUARDO',
    phone: '50769504792',
    waText: 'Hola Eduardo, buen día. Te escribo porque necesito tu asistencia con unos productos Thule y WeatherTech. ¿Me puedes orientar por favor?',
  },
];

const buildWaUrl = (phone, text) => `https://api.whatsapp.com/send?phone=${phone}&text=${encodeURIComponent(text)}`;

const findAdvisorByPayload = (inboundText) => {
  const inboundUpper = String(inboundText || '').trim().toUpperCase();
  return SALES_ADVISORS.find((a) => inboundUpper === `QR:${a.qrPayload}`) || null;
};

const stripAdvisorLinks = (text) => String(text || '')
  .replace(/\[ADVISOR_MENU\]/gi, '')
  .replace(/https?:\/\/(?:api\.)?whatsapp\.com\/send[^\s)\]]+/gi, '')
  .replace(/^\s*[-•*]\s*(Dave|Eduardo)\s*:?\s*$/gim, '')
  .replace(/\n{3,}/g, '\n\n')
  .trim();
