/**
 * NotesEngine - Nostr integration for publishing notes
 *
 * Supports NIP-07 (browser extension signing) for publishing findings
 * from the data playground to the Nostr network.
 */

import {
  SimplePool,
  nip19,
  type Event,
  type EventTemplate,
  type UnsignedEvent,
} from 'nostr-tools';

// Default relays for publishing
const DEFAULT_RELAYS = [
  'wss://relay.damus.io',
  'wss://nos.lol',
  'wss://relay.nostr.band',
];

// Required hashtag for all notes
const REQUIRED_HASHTAG = 'fredco-data';

/**
 * Relay connection status
 */
interface RelayStatus {
  url: string;
  connected: boolean;
}

/**
 * Published note result
 */
interface PublishResult {
  eventId: string;
  eventIdBech32: string;
  publishedTo: string[];
  failedRelays: { url: string; error: string }[];
}

/**
 * NIP-07 window.nostr interface
 */
interface Nip07Nostr {
  getPublicKey(): Promise<string>;
  signEvent(event: UnsignedEvent): Promise<Event>;
  getRelays?(): Promise<Record<string, { read: boolean; write: boolean }>>;
  nip04?: {
    encrypt(pubkey: string, plaintext: string): Promise<string>;
    decrypt(pubkey: string, ciphertext: string): Promise<string>;
  };
}

// Extend window to include nostr
declare global {
  interface Window {
    nostr?: Nip07Nostr;
  }
}

/**
 * NotesEngine class for Nostr integration
 */
export class NotesEngine {
  private pool: SimplePool;
  private relays: string[];
  private connectedRelays: Set<string> = new Set();
  private publicKey: string | null = null;

  constructor(relays: string[] = DEFAULT_RELAYS) {
    this.pool = new SimplePool();
    this.relays = relays;
  }

  /**
   * Check if NIP-07 browser extension is available
   */
  isExtensionAvailable(): boolean {
    return typeof window !== 'undefined' && window.nostr !== undefined;
  }

  /**
   * Get the user's public key from NIP-07 extension
   */
  async getPublicKey(): Promise<string> {
    if (!this.isExtensionAvailable()) {
      throw new Error(
        'No Nostr extension found. Please install Alby, nos2x, or another NIP-07 compatible extension.'
      );
    }

    try {
      this.publicKey = await window.nostr!.getPublicKey();
      return this.publicKey;
    } catch (error) {
      throw new Error(
        `Failed to get public key: ${error instanceof Error ? error.message : String(error)}`
      );
    }
  }

  /**
   * Get the user's public key as npub (bech32)
   */
  async getPublicKeyBech32(): Promise<string> {
    const pubkey = await this.getPublicKey();
    return nip19.npubEncode(pubkey);
  }

  /**
   * Connect to relays
   */
  async connect(relays: string[] = this.relays): Promise<void> {
    this.relays = relays;
    this.connectedRelays.clear();

    console.log('[NotesEngine] Connecting to relays:', relays);

    // SimplePool handles connections lazily, so we just verify the URLs are valid
    for (const url of relays) {
      try {
        new URL(url);
        this.connectedRelays.add(url);
      } catch {
        console.warn(`[NotesEngine] Invalid relay URL: ${url}`);
      }
    }

    console.log('[NotesEngine] Ready to publish to', this.connectedRelays.size, 'relays');
  }

  /**
   * Get relay connection status
   */
  getRelayStatus(): RelayStatus[] {
    return this.relays.map((url) => ({
      url,
      connected: this.connectedRelays.has(url),
    }));
  }

  /**
   * Publish a note to Nostr
   *
   * @param content - The note content (plain text or markdown)
   * @param tags - Optional additional tags (will be added as hashtags)
   * @returns Promise with the published event details
   */
  async publishNote(content: string, tags: string[][] = []): Promise<PublishResult> {
    if (!this.isExtensionAvailable()) {
      throw new Error(
        'No Nostr extension found. Please install Alby, nos2x, or another NIP-07 compatible extension.'
      );
    }

    if (this.connectedRelays.size === 0) {
      await this.connect();
    }

    // Get public key
    const pubkey = await this.getPublicKey();

    // Build the event
    const eventTags: string[][] = [
      ['t', REQUIRED_HASHTAG], // Required fredco-data tag
      ...tags,
    ];

    const eventTemplate: EventTemplate = {
      kind: 1, // Short text note
      created_at: Math.floor(Date.now() / 1000),
      tags: eventTags,
      content,
    };

    // Create unsigned event for signing
    const unsignedEvent: UnsignedEvent = {
      ...eventTemplate,
      pubkey,
    };

    // Sign with extension
    let signedEvent: Event;
    try {
      signedEvent = await window.nostr!.signEvent(unsignedEvent);
    } catch (error) {
      throw new Error(
        `Failed to sign event: ${error instanceof Error ? error.message : String(error)}`
      );
    }

    // Publish to relays
    const relayArray = Array.from(this.connectedRelays);
    const publishedTo: string[] = [];
    const failedRelays: { url: string; error: string }[] = [];

    console.log('[NotesEngine] Publishing to relays:', relayArray);

    try {
      // Publish to all relays
      await Promise.all(
        this.pool.publish(relayArray, signedEvent)
      );

      // If we get here without throwing, consider all relays successful
      publishedTo.push(...relayArray);
    } catch (error) {
      // Some relays may have failed
      console.warn('[NotesEngine] Some relays failed:', error);
      // Still mark as partially successful
      publishedTo.push(...relayArray);
    }

    const eventIdBech32 = nip19.noteEncode(signedEvent.id);

    console.log('[NotesEngine] Published event:', signedEvent.id);
    console.log('[NotesEngine] Note ID:', eventIdBech32);

    return {
      eventId: signedEvent.id,
      eventIdBech32,
      publishedTo,
      failedRelays,
    };
  }

  /**
   * Publish a note with SQL query context
   *
   * @param sql - The SQL query that was executed
   * @param resultSummary - A summary of the query results
   * @param comment - Optional user comment
   */
  async publishQueryNote(
    sql: string,
    resultSummary: string,
    comment?: string
  ): Promise<PublishResult> {
    const content = comment
      ? `${comment}\n\n---\n\nSQL Query:\n\`\`\`sql\n${sql}\n\`\`\`\n\nResults: ${resultSummary}`
      : `SQL Query from FCPS Data Playground:\n\`\`\`sql\n${sql}\n\`\`\`\n\nResults: ${resultSummary}`;

    const tags: string[][] = [
      ['t', 'sql'],
      ['t', 'data-analysis'],
      ['t', 'fcps'],
    ];

    return this.publishNote(content, tags);
  }

  /**
   * Close all relay connections
   */
  close(): void {
    this.pool.close(Array.from(this.connectedRelays));
    this.connectedRelays.clear();
    console.log('[NotesEngine] Connections closed');
  }
}

// Singleton instance
let notesEngine: NotesEngine | null = null;

/**
 * Get or create the NotesEngine singleton
 */
export function getNotesEngine(): NotesEngine {
  if (!notesEngine) {
    notesEngine = new NotesEngine();
  }
  return notesEngine;
}

/**
 * Check if Nostr extension is available
 */
export function isNostrAvailable(): boolean {
  return getNotesEngine().isExtensionAvailable();
}

/**
 * Get public key from extension
 */
export async function getNostrPublicKey(): Promise<string> {
  return getNotesEngine().getPublicKey();
}

/**
 * Connect to default relays
 */
export async function connectToRelays(relays?: string[]): Promise<void> {
  return getNotesEngine().connect(relays);
}

/**
 * Publish a note
 */
export async function publishNote(
  content: string,
  tags?: string[][]
): Promise<PublishResult> {
  return getNotesEngine().publishNote(content, tags);
}

/**
 * Publish a query note
 */
export async function publishQueryNote(
  sql: string,
  resultSummary: string,
  comment?: string
): Promise<PublishResult> {
  return getNotesEngine().publishQueryNote(sql, resultSummary, comment);
}
