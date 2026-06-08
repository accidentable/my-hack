"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { uploadCard } from "@/lib/api";

const ACCEPTED_RE = /^(image\/(png|jpe?g|webp)|video\/.*)$/i;

export default function UploadPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [language, setLanguage] = useState("ko");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Object URL lifecycle — revoke previous on change/unmount.
  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function acceptFile(f: File | null | undefined) {
    if (!f) return;
    if (!ACCEPTED_RE.test(f.type)) {
      setError(`지원되지 않는 형식 · ${f.type || "unknown"}`);
      return;
    }
    setError(null);
    setFile(f);
  }

  function onDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files?.[0];
    acceptFile(dropped);
  }

  async function handleSubmit() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const started = await uploadCard(file, language);
      router.push(`/review/${started.thread_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  const isVideo = file?.type.startsWith("video/") ?? false;

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-2xl font-semibold tracking-tight">사전 심의 시작</h1>
      <p className="mt-2 text-sm text-muted">
        대고객 콘텐츠(카드뉴스·릴스 등) 파일을 올리면, 적용 규정을 자동으로 찾아
        위반 소지·근거·수정안을 정리합니다. 최종 결정은 준법관리자가 합니다.
      </p>

      <div className="mt-8 space-y-5">
        {/* 드롭존 + 파일 선택 */}
        <div>
          <label className="block text-sm font-medium text-ink">콘텐츠 파일</label>

          <div
            onClick={() => inputRef.current?.click()}
            onDragEnter={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={(e) => {
              // ignore drag-leave fired by entering a child element
              if (e.currentTarget.contains(e.relatedTarget as Node)) return;
              setDragOver(false);
            }}
            onDrop={onDrop}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
            }}
            className={`mt-2 cursor-pointer rounded-md border border-dashed transition-colors ${
              dragOver
                ? "border-brand bg-brand-weak"
                : "border-line bg-bg hover:border-soft"
            }`}
          >
            {/* 미리보기 또는 안내 */}
            {file && previewUrl ? (
              <div className="flex items-stretch gap-4 p-4">
                <div className="h-28 w-28 shrink-0 overflow-hidden rounded border border-line bg-white">
                  {isVideo ? (
                    <video
                      src={previewUrl}
                      muted
                      playsInline
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={previewUrl}
                      alt={file.name}
                      className="h-full w-full object-cover"
                    />
                  )}
                </div>
                <div className="flex min-w-0 flex-col justify-between py-1">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-ink">
                      {file.name}
                    </p>
                    <p className="mt-1 text-xs text-soft">
                      {(file.size / 1024).toFixed(0)} KB · {file.type || "—"}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={(ev) => {
                      ev.stopPropagation();
                      setFile(null);
                      if (inputRef.current) inputRef.current.value = "";
                    }}
                    className="self-start text-xs font-medium text-muted hover:text-ink"
                  >
                    다른 파일 선택
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between px-4 py-5">
                <div>
                  <p className="text-sm text-muted">
                    {dragOver ? "여기에 놓아주세요" : "이미지·영상 파일을 끌어다 놓거나 클릭해 선택"}
                  </p>
                  <p className="mt-1 text-xs text-soft">
                    PNG · JPG · MP4 등 · 한 개
                  </p>
                </div>
                <span className="text-xs font-medium text-brand">파일 선택</span>
              </div>
            )}
          </div>

          <input
            ref={inputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp,video/*"
            onChange={(e) => acceptFile(e.target.files?.[0])}
            className="hidden"
          />
        </div>

        {/* 언어 */}
        <div>
          <label className="block text-sm font-medium text-ink">콘텐츠 언어</label>
          <div className="mt-2 inline-flex rounded-md border border-line overflow-hidden">
            {[
              { v: "ko", label: "한국어" },
              { v: "vi", label: "베트남어" },
              { v: "", label: "자동 판별" },
            ].map((opt) => (
              <button
                key={opt.v || "auto"}
                type="button"
                onClick={() => setLanguage(opt.v)}
                className={`px-3 py-1.5 text-sm transition-colors ${
                  language === opt.v
                    ? "bg-ink text-white"
                    : "bg-white text-muted hover:text-ink"
                } ${opt.v !== "" ? "border-r border-line" : ""}`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {error && <p className="text-sm text-sev-high">{error}</p>}

        <div className="pt-2">
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!file || busy}
            className="w-full rounded-md bg-brand px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-brand-hover disabled:bg-soft"
          >
            {busy ? "시작 중..." : "심의 시작"}
          </button>
        </div>
      </div>
    </div>
  );
}
