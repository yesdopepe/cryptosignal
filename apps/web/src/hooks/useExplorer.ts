'use client';

import { create } from 'zustand';

interface ExplorerState {
  isOpen: boolean;
  chain: string | undefined;
  address: string | undefined;
  openExplorer: (chain: string | undefined, address: string) => void;
  closeExplorer: () => void;
}

export const useExplorer = create<ExplorerState>((set) => ({
  isOpen: false,
  chain: undefined,
  address: undefined,
  openExplorer: (chain, address) => set({ isOpen: true, chain, address }),
  closeExplorer: () => set({ isOpen: false }),
}));