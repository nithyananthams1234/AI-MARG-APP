import { jest } from '@jest/globals';

describe('SQLite-backed key-value storage', () => {
  afterEach(() => {
    jest.dontMock('expo-sqlite/kv-store');
    jest.resetModules();
  });

  it('does not import the native SQLite module while loading storage utilities', () => {
    const loadStore = jest.fn(() => {
      throw new Error('SQLite module should be loaded only when storage is used.');
    });
    jest.doMock('expo-sqlite/kv-store', loadStore);

    let kv!: typeof import('@/lib/storage').kv;
    jest.isolateModules(() => {
      kv = jest.requireActual<typeof import('@/lib/storage')>('@/lib/storage').kv;
    });

    expect(loadStore).not.toHaveBeenCalled();
    expect(typeof kv.get).toBe('function');
    expect(typeof kv.set).toBe('function');
    expect(typeof kv.remove).toBe('function');
  });
});
