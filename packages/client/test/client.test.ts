import axios from 'axios';
import { EngramClient } from '../src/client';
import { HybridEncryption, generateKeypair } from '../src/crypto';

jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('EngramClient', () => {
  let client: EngramClient;

  beforeEach(() => {
    // Reset mock
    mockedAxios.create.mockReturnValue(mockedAxios);
    mockedAxios.post.mockReset();
    mockedAxios.get.mockReset();
    client = new EngramClient({ minerUrl: 'http://localhost:8091' });
  });

  it('ingest() should return a CID', async () => {
    mockedAxios.post.mockResolvedValueOnce({ data: { cid: 'v1::abc' } });
    const cid = await client.ingest('test text');
    expect(cid).toBe('v1::abc');
    expect(mockedAxios.post).toHaveBeenCalledWith('/IngestSynapse', expect.any(Object));
  });

  it('query() should return results', async () => {
    mockedAxios.post.mockResolvedValueOnce({ data: { results: [{ cid: 'v1::abc', score: 0.9 }] } });
    const results = await client.query('test text');
    expect(results).toHaveLength(1);
    expect(results[0].cid).toBe('v1::abc');
  });

  it('should encrypt and decrypt using HybridEncryption', async () => {
    const { privateKey } = generateKeypair();
    const enc = new HybridEncryption(privateKey);
    const encrypted = enc.encryptPayload('secret', { type: 'text' });
    const decrypted = enc.decryptPayload(encrypted);
    expect(decrypted.text).toBe('secret');
    expect(decrypted.metadata.type).toBe('text');
  });

  it('should throw when trying to ingest with HybridEncryption directly', async () => {
    const { privateKey } = generateKeypair();
    const enc = new HybridEncryption(privateKey);
    const encryptedClient = new EngramClient({ encryption: enc });

    await expect(encryptedClient.ingest('test text')).rejects.toThrow(
      'Private namespaces require local embedding. Please compute your embedding and use ingestEmbedding().'
    );
  });
});
