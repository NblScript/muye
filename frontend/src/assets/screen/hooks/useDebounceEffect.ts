import { useEffect, useRef } from "react";

export function useDebounceEffect(
  effect: () => void | (() => void),
  deps: unknown[],
  delay: number
) {
  const cleanupRef = useRef<void | (() => void)>(null);

  useEffect(() => {
    const handler = setTimeout(() => {
      // 触发副作用
      cleanupRef.current = effect();
    }, delay);

    return () => {
      clearTimeout(handler);
      // 执行上一次 effect 的 cleanup
      if (cleanupRef.current) {
        cleanupRef.current();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, delay]);
}
