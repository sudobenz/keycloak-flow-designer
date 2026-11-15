/**
 * Génère un UUID v4 utilisable aussi lorsque l'application est servie en HTTP.
 * crypto.randomUUID() est limité aux contextes sécurisés (HTTPS/localhost).
 * getRandomValues() reste disponible dans les contextes non sécurisés.
 */
export function createUuid() {
    const cryptoApi = globalThis.crypto;
    if (typeof cryptoApi?.randomUUID === 'function') {
        return cryptoApi.randomUUID();
    }
    if (typeof cryptoApi?.getRandomValues === 'function') {
        const bytes = new Uint8Array(16);
        cryptoApi.getRandomValues(bytes);
        bytes[6] = (bytes[6] & 0x0f) | 0x40; // UUID version 4
        bytes[8] = (bytes[8] & 0x3f) | 0x80; // RFC 4122 variant
        const hex = Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('');
        return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
    }
    // Dernier recours pour les navigateurs très anciens : ces identifiants ne sont
    // pas des secrets et servent uniquement d'identifiants locaux de nœuds/projets.
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, marker => {
        const value = Math.floor(Math.random() * 16);
        return (marker === 'x' ? value : (value & 0x3) | 0x8).toString(16);
    });
}
