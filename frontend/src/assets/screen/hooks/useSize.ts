import { useLayoutEffect, useState } from "react";

const useSize = (ref: React.RefObject<HTMLDivElement | null>) => {
  const [windowSize, setWindowSize] = useState({ width: 0, height: 0 });

  useLayoutEffect(() => {
    if (!ref.current) return;
    const observer = new ResizeObserver(([entry]) => {
      setWindowSize({
        width: entry.contentRect.width,
        height: entry.contentRect.height,
      });
    });

    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [ref]);

  return windowSize;
};

export default useSize;
