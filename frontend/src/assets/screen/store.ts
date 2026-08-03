import { create } from "zustand";
import { subscribeWithSelector } from "zustand/middleware";

interface ConfigStore {
  mapPlayComplete: boolean;
  cloud: boolean;
  bar: boolean;
  rotation: boolean;
  heat: boolean;
  drone: boolean;
  mode: boolean;
  toggle: (key: keyof Omit<ConfigStore, "toggle">) => void;
  reset: () => void;
}

export const useConfigStore = create<ConfigStore>()(
  subscribeWithSelector((set, _, store) => ({
    mapPlayComplete: false,
    cloud: true,
    bar: true,
    rotation: true,
    heat: true,
    drone: true,
    mode: true,
    toggle: (key) => set((s) => ({ [key]: !s[key] })),
    reset: () => set(store.getInitialState()),
  }))
);
