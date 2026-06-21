import * as crypto from 'crypto';
import nacl from 'tweetnacl';

const KEY_LEN = 32;
const IV_LEN = 12;
const X25519_LEN = 32;
const HKDF_INFO = 'engram-hybrid-v1';

function aesGcmEncrypt(key: Buffer, plaintext: Buffer): Buffer {
  const iv = crypto.randomBytes(IV_LEN);
  const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);
  const ciphertext = Buffer.concat([cipher.update(plaintext), cipher.final()]);
  const tag = cipher.getAuthTag();
  return Buffer.concat([iv, ciphertext, tag]);
}

function aesGcmDecrypt(key: Buffer, blob: Buffer): Buffer {
  if (blob.length < IV_LEN + 16) {
    throw new Error('Decryption failed — blob too short.');
  }
  const iv = blob.subarray(0, IV_LEN);
  const ciphertext = blob.subarray(IV_LEN, blob.length - 16);
  const tag = blob.subarray(blob.length - 16);
  const decipher = crypto.createDecipheriv('aes-256-gcm', key, iv);
  decipher.setAuthTag(tag);
  try {
    return Buffer.concat([decipher.update(ciphertext), decipher.final()]);
  } catch (err) {
    throw new Error('Decryption failed — data may be tampered or the key is wrong.');
  }
}

function hkdf(sharedSecret: Buffer, salt: Buffer): Buffer {
  return Buffer.from(crypto.hkdfSync('sha256', sharedSecret, salt, HKDF_INFO, KEY_LEN));
}

function serializePayload(text: string | null, metadata: Record<string, any>): Buffer {
  return Buffer.from(JSON.stringify({ text: text || "", metadata }), 'utf-8');
}

function deserializePayload(data: Buffer): { text: string; metadata: Record<string, any> } {
  const payload = JSON.parse(data.toString('utf-8'));
  return { text: payload.text || "", metadata: payload.metadata || {} };
}

export function generateKeypair(): { privateKey: Buffer; publicKey: Buffer } {
  const keyPair = nacl.box.keyPair();
  return {
    privateKey: Buffer.from(keyPair.secretKey),
    publicKey: Buffer.from(keyPair.publicKey)
  };
}

export function publicKeyFromPrivate(privateKeyBytes: Buffer): Buffer {
  return Buffer.from(nacl.scalarMult.base(new Uint8Array(privateKeyBytes)));
}

export class HybridEncryption {
  private _privateKey?: Buffer;
  private _publicKey?: Buffer;

  constructor(privateKey?: Buffer, publicKey?: Buffer) {
    if (!privateKey && !publicKey) {
      throw new Error('HybridEncryption requires at least one of: privateKey, publicKey');
    }
    this._privateKey = privateKey;
    if (publicKey) {
      this._publicKey = publicKey;
    } else if (privateKey) {
      this._publicKey = publicKeyFromPrivate(privateKey);
    }
  }

  encryptPayload(text: string | null, metadata: Record<string, any>): string {
    const ephemeralPair = generateKeypair();
    
    // ECDH with recipient public key
    const sharedSecret = Buffer.from(nacl.scalarMult(
      new Uint8Array(ephemeralPair.privateKey),
      new Uint8Array(this._publicKey!)
    ));

    // HKDF
    const aesKey = hkdf(sharedSecret, ephemeralPair.publicKey);

    // AES-256-GCM encrypt
    const encrypted = aesGcmEncrypt(aesKey, serializePayload(text, metadata));

    // Wire: ephemeral_public || iv || ciphertext+tag
    const wire = Buffer.concat([ephemeralPair.publicKey, encrypted]);
    return wire.toString('base64url');
  }

  decryptPayload(blob: string): { text: string; metadata: Record<string, any> } {
    if (!this._privateKey) {
      throw new Error('This HybridEncryption instance has no private key — it can encrypt but not decrypt.');
    }
    
    const raw = Buffer.from(blob, 'base64url');
    if (raw.length < X25519_LEN + IV_LEN + 16) {
      throw new Error('Decryption failed — blob too short.');
    }

    const ephemeralPubBytes = raw.subarray(0, X25519_LEN);
    const encrypted = raw.subarray(X25519_LEN);

    // ECDH with our private key
    const sharedSecret = Buffer.from(nacl.scalarMult(
      new Uint8Array(this._privateKey),
      new Uint8Array(ephemeralPubBytes)
    ));

    // HKDF
    const aesKey = hkdf(sharedSecret, ephemeralPubBytes);

    // AES-256-GCM decrypt
    const plaintext = aesGcmDecrypt(aesKey, encrypted);
    return deserializePayload(plaintext);
  }

  encryptRaw(data: Buffer): Buffer {
    const ephemeralPair = generateKeypair();
    const sharedSecret = Buffer.from(nacl.scalarMult(
      new Uint8Array(ephemeralPair.privateKey),
      new Uint8Array(this._publicKey!)
    ));
    const aesKey = hkdf(sharedSecret, ephemeralPair.publicKey);
    return Buffer.concat([ephemeralPair.publicKey, aesGcmEncrypt(aesKey, data)]);
  }

  decryptRaw(data: Buffer): Buffer {
    if (!this._privateKey) {
      throw new Error('No private key — cannot decrypt raw bytes.');
    }
    const ephemeralPubBytes = data.subarray(0, X25519_LEN);
    const encrypted = data.subarray(X25519_LEN);
    const sharedSecret = Buffer.from(nacl.scalarMult(
      new Uint8Array(this._privateKey),
      new Uint8Array(ephemeralPubBytes)
    ));
    const aesKey = hkdf(sharedSecret, ephemeralPubBytes);
    return aesGcmDecrypt(aesKey, encrypted);
  }

  decryptResults(results: any[]): any[] {
    return results.map(r => {
      const meta = r.metadata || {};
      const blob = meta._enc;
      if (blob) {
        try {
          const { metadata: decryptedMeta } = this.decryptPayload(blob);
          return { ...r, metadata: decryptedMeta };
        } catch (e) {
          return { ...r, metadata: { _error: 'decryption_failed' } };
        }
      }
      return r;
    });
  }
}
