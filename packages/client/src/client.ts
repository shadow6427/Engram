import axios, { AxiosInstance } from 'axios';
import { KeyringPair } from '@polkadot/keyring/types';
import { u8aToHex, stringToU8a } from '@polkadot/util';
import {
  EngramError,
  IngestError,
  InvalidCIDError,
  MinerOfflineError,
  QueryError,
} from './errors';
import { HybridEncryption } from './crypto';

export interface EngramClientOptions {
  minerUrl?: string;
  timeout?: number;
  namespace?: string;
  namespaceKey?: string;
  encryption?: HybridEncryption;
  keypair?: KeyringPair;
}

export class EngramClient {
  public minerUrl: string;
  public timeout: number;
  public namespace?: string;
  public namespaceKey?: string;
  private _keypair?: KeyringPair;
  private _enc?: HybridEncryption;
  private _http: AxiosInstance;

  constructor(options: EngramClientOptions = {}) {
    this.minerUrl = (options.minerUrl || 'http://127.0.0.1:8091').replace(/\/$/, '');
    this.timeout = options.timeout || 30000;
    this.namespace = options.namespace;
    this.namespaceKey = options.namespaceKey;
    this._keypair = options.keypair;
    this._enc = options.encryption;

    this._http = axios.create({
      baseURL: this.minerUrl,
      timeout: this.timeout,
    });

    this._http.interceptors.response.use(
      (response) => response,
      (error) => {
        if (!error.response) {
          throw new MinerOfflineError(this.minerUrl, error);
        }
        throw error;
      }
    );
  }

  private _namespaceAuth(): Record<string, any> {
    if (!this.namespace) {
      return {};
    }
    if (this._keypair) {
      const ts = Date.now();
      const msg = `engram-ns:${this.namespace}:${ts}`;
      const sigRaw = this._keypair.sign(stringToU8a(msg));
      const sig = u8aToHex(sigRaw);
      return {
        namespace: this.namespace,
        namespace_hotkey: this._keypair.address,
        namespace_sig: sig,
        namespace_timestamp_ms: ts,
      };
    }
    return {
      namespace: this.namespace,
      namespace_key: this.namespaceKey,
    };
  }

  private _validateCid(cid: string): void {
    if (!cid.startsWith('v1::') && !cid.startsWith('v0::')) {
      throw new InvalidCIDError(cid);
    }
  }

  private async _post(endpoint: string, payload: Record<string, any>): Promise<any> {
    try {
      const res = await this._http.post(`/${endpoint}`, payload);
      return res.data;
    } catch (err: any) {
      if (err instanceof MinerOfflineError) throw err;
      if (err.response && err.response.data) {
        return err.response.data; // Server might return { error: ... } with 400
      }
      throw new EngramError(`POST request failed: ${err.message}`);
    }
  }

  private async _get(endpoint: string): Promise<any> {
    try {
      const res = await this._http.get(`/${endpoint}`);
      return res.data;
    } catch (err: any) {
      if (err instanceof MinerOfflineError) throw err;
      if (err.response && err.response.data) {
        return err.response.data;
      }
      throw new EngramError(`GET request failed: ${err.message}`);
    }
  }

  public async ingest(text: string, metadata?: Record<string, any>): Promise<string> {
    let payload: Record<string, any>;
    if (this._enc) {
      // In JS SDK we don't auto-embed like Python. The user must use ingestEmbedding if using private namespace with pure JS client, 
      // or we just send the text and let the miner embed it (Wait, Python's EnramClient locally embeds if _enc is set).
      // Since JS has no sentence-transformers out of the box, we throw if _enc is set and ingest() is called instead of ingestEmbedding().
      throw new Error("Private namespaces require local embedding. Please compute your embedding and use ingestEmbedding().");
    } else {
      payload = { text, metadata: metadata || {} };
    }

    const data = await this._post('IngestSynapse', { ...payload, ...this._namespaceAuth() });
    
    if (data.error) {
      throw new IngestError(data.error);
    }
    if (!data.cid) {
      throw new IngestError('Miner returned no CID and no error');
    }

    this._validateCid(data.cid);
    return data.cid;
  }

  public async ingestEmbedding(embedding: number[], metadata?: Record<string, any>): Promise<string> {
    let payload: Record<string, any>;
    if (this._enc) {
      const encBlob = this._enc.encryptPayload(null, metadata || {});
      payload = {
        raw_embedding: embedding,
        metadata: { _enc: encBlob },
      };
    } else {
      payload = {
        raw_embedding: embedding,
        metadata: metadata || {},
      };
    }

    const data = await this._post('IngestSynapse', { ...payload, ...this._namespaceAuth() });
    
    if (data.error) {
      throw new IngestError(data.error);
    }
    if (!data.cid) {
      throw new IngestError('Miner returned no CID and no error');
    }

    this._validateCid(data.cid);
    return data.cid;
  }

  public async query(text: string, topK: number = 10, filter?: Record<string, string>): Promise<any[]> {
    if (this._enc) {
      throw new Error("Private namespaces require local embedding. Please compute your query embedding and use queryByVector().");
    }

    const payload: Record<string, any> = { query_text: text, top_k: topK, ...this._namespaceAuth() };
    if (filter) payload.filter = filter;

    const data = await this._post('QuerySynapse', payload);
    if (data.error) throw new QueryError(data.error);

    return data.results || [];
  }

  public async queryByVector(vector: number[], topK: number = 10, filter?: Record<string, string>): Promise<any[]> {
    const payload: Record<string, any> = { query_vector: vector, top_k: topK, ...this._namespaceAuth() };
    if (filter) payload.filter = filter;

    const data = await this._post('QuerySynapse', payload);
    if (data.error) throw new QueryError(data.error);

    let results = data.results || [];
    if (this._enc) {
      results = this._enc.decryptResults(results);
    }
    return results;
  }

  public async get(cid: string): Promise<Record<string, any>> {
    const encodedCid = encodeURIComponent(cid);
    const result = await this._get(`retrieve/${encodedCid}`);
    if (result.error) throw new Error(`CID not found: ${cid}`);
    return result;
  }

  public async delete(cid: string): Promise<boolean> {
    const encodedCid = encodeURIComponent(cid);
    try {
      const res = await this._http.delete(`/retrieve/${encodedCid}`);
      return res.data?.deleted || false;
    } catch (err: any) {
      if (err instanceof MinerOfflineError) throw err;
      if (err.response?.status === 404) return false;
      throw new EngramError(`Delete request failed: ${err.message}`);
    }
  }

  public async list(filter?: Record<string, string>, limit: number = 50, offset: number = 0): Promise<any[]> {
    const payload: Record<string, any> = { limit, offset };
    if (filter) payload.filter = filter;
    if (this.namespace) payload.namespace = this.namespace;
    
    const data = await this._post('list', payload);
    return data.records || [];
  }

  public async health(): Promise<Record<string, any>> {
    return this._get('health');
  }

  public async isOnline(): Promise<boolean> {
    try {
      await this.health();
      return true;
    } catch {
      return false;
    }
  }
}
