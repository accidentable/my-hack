"use client";

import { isVideoSource } from "@/lib/api";

/**
 * 원본 콘텐츠 미리보기.
 * - 이미지: <img>
 * - 영상: <video controls>
 * - 부모(좌측 컬럼)에서 sticky 처리. 여기는 내용물만.
 */
export function OriginalPreview({
  url,
  caption,
}: {
  url: string;
  caption?: string;
}) {
  const isVideo = isVideoSource({ url });
  return (
    <figure className="space-y-3">
      <div className="overflow-hidden rounded-md border border-line bg-bg">
        {isVideo ? (
          <video
            src={url}
            controls
            playsInline
            className="block max-h-[70vh] w-full object-contain bg-black"
          />
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={url}
            alt={caption ?? "원본 콘텐츠"}
            className="block max-h-[70vh] w-full object-contain"
          />
        )}
      </div>
      <figcaption className="text-xs text-soft">
        {caption ?? "심의 대상 원본"}
      </figcaption>
    </figure>
  );
}
