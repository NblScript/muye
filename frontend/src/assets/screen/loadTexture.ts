import { TextureLoader, type Texture } from "three";

export default function loadTexture(
  url: string,
  onLoad?: (texture: Texture<HTMLImageElement>) => void
): Promise<Texture<HTMLImageElement>> {
  return new Promise((resolve, reject) => {
    new TextureLoader().load(
      url,
      (tex) => {
        onLoad?.(tex);
        resolve(tex);
      },
      undefined,
      reject
    );
  });
}
