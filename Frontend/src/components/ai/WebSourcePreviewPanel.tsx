import { useState, useEffect, useRef } from 'react';
import {
  Check,
  Copy,
  ExternalLink,
  Globe,
  Lock,
  RefreshCw,
  ShieldCheck,
  X,
  FileText,
  AlertTriangle,
  RotateCcw,
} from 'lucide-react';
import type { SourceCitation } from '@/utils/sourceCitationParser';

interface WebSourcePreviewPanelProps {
  source: SourceCitation | null;
  onClose: () => void;
  className?: string;
}

/**
 * Validates whether a given string is a valid http(s) URL.
 */
function isValidHttpUrl(url?: string): boolean {
  if (!url) return false;
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

export function WebSourcePreviewPanel({
  source,
  onClose,
  className = '',
}: WebSourcePreviewPanelProps) {
  const [copied, setCopied] = useState(false);
  const [iframeLoading, setIframeLoading] = useState(true);
  const [iframeBlocked, setIframeBlocked] = useState(false);
  const [activeTab, setActiveTab] = useState<'embed' | 'info'>('embed');
  const [reloadKey, setReloadKey] = useState(0);
  const timeoutRef = useRef<number | null>(null);

  const hasValidUrl = Boolean(source?.url && isValidHttpUrl(source.url));

  useEffect(() => {
    // Reset all states when selected source changes
    setIframeLoading(true);
    setIframeBlocked(false);
    setCopied(false);
    setActiveTab(hasValidUrl && !source?.isInternal ? 'embed' : 'info');

    if (timeoutRef.current) {
      window.clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }

    // Fallback timer: if iframe does not finish loading within 8 seconds (common for CSP / X-Frame-Options blocks)
    if (hasValidUrl && !source?.isInternal) {
      timeoutRef.current = window.setTimeout(() => {
        setIframeLoading(false);
      }, 8000);
    }

    return () => {
      if (timeoutRef.current) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, [source?.url, source?.id, reloadKey, hasValidUrl, source?.isInternal]);

  const handleCopyUrl = async () => {
    if (!source?.url) return;
    try {
      await navigator.clipboard.writeText(source.url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback if clipboard API is restricted
      const textarea = document.createElement('textarea');
      textarea.value = source.url;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleRetryIframe = () => {
    setIframeBlocked(false);
    setIframeLoading(true);
    setReloadKey((k) => k + 1);
  };

  if (!source) {
    return (
      <aside
        className={`flex h-full min-h-0 flex-col overflow-hidden rounded-2xl sm:rounded-3xl border border-slate-200 bg-white shadow-card ${className}`}
      >
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3 bg-slate-50/50">
          <div className="flex items-center gap-2">
            <Globe size={18} className="text-slate-400" />
            <h2 className="text-sm font-bold text-slate-800">Web Source Preview</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition"
            title="Đóng panel"
            aria-label="Đóng"
          >
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-slate-400">
          <Globe size={40} className="mb-3 text-slate-300 stroke-1" />
          <p className="text-sm font-semibold text-slate-600">Chưa chọn nguồn tham khảo</p>
          <p className="mt-1 text-xs text-slate-400 max-w-[220px]">
            Bấm vào các liên kết nguồn (Nguồn tham khảo / Citations) trong câu trả lời AI để xem preview website tại đây.
          </p>
        </div>
      </aside>
    );
  }

  return (
    <aside
      className={`flex h-full min-h-0 flex-col overflow-hidden rounded-2xl sm:rounded-3xl border border-slate-200 bg-white shadow-card ${className}`}
      aria-label="Web Source Preview Panel"
    >
      {/* 1. Header */}
      <header className="flex items-center justify-between border-b border-slate-100 px-4 py-3 bg-slate-50/80 shrink-0">
        <div className="flex items-center gap-2.5 min-w-0 pr-2">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-emerald-100 text-emerald-800">
            {source.isInternal ? <FileText size={16} /> : <Globe size={16} />}
          </span>
          <div className="min-w-0">
            <h2 className="text-xs sm:text-sm font-bold text-slate-900 truncate" title={source.name}>
              {source.name}
            </h2>
            <div className="flex items-center gap-1.5 mt-0.5">
              {source.domain && (
                <span className="inline-flex items-center gap-1 rounded bg-slate-200/80 px-1.5 py-0.2 text-[10.5px] font-medium text-slate-700">
                  <Lock size={10} className="text-slate-500" />
                  {source.domain}
                </span>
              )}
              {source.collectedAt && (
                <span className="text-[10px] text-slate-400 truncate">
                  Cập nhật: {source.collectedAt}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          {hasValidUrl && (
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-200/70 hover:text-brand-700 transition"
              title="Mở trong tab mới"
            >
              <ExternalLink size={15} />
            </a>
          )}
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-200/70 hover:text-slate-800 transition"
            title="Đóng panel"
            aria-label="Đóng panel"
          >
            <X size={17} />
          </button>
        </div>
      </header>

      {/* Mode switcher tabs (Embed vs Information) if URL is valid */}
      {hasValidUrl && !source.isInternal && (
        <div className="flex items-center justify-between border-b border-slate-100 bg-white px-3 py-1.5 gap-2 text-xs shrink-0">
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => setActiveTab('embed')}
              className={`px-2.5 py-1 rounded-lg font-semibold transition ${
                activeTab === 'embed'
                  ? 'bg-emerald-50 text-emerald-900 border border-emerald-200 shadow-2xs'
                  : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'
              }`}
            >
              Trang web (Embed)
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('info')}
              className={`px-2.5 py-1 rounded-lg font-semibold transition ${
                activeTab === 'info'
                  ? 'bg-emerald-50 text-emerald-900 border border-emerald-200 shadow-2xs'
                  : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'
              }`}
            >
              Thông tin nguồn
            </button>
          </div>

          {activeTab === 'embed' && (
            <button
              type="button"
              onClick={handleRetryIframe}
              className="p-1 text-slate-400 hover:text-slate-700 rounded transition"
              title="Tải lại trang web"
            >
              <RotateCcw size={13} />
            </button>
          )}
        </div>
      )}

      {/* 2. Scrollable Body Preview */}
      <div className="flex-1 min-h-0 relative overflow-y-auto bg-slate-50/50">
        {hasValidUrl && !source.isInternal && activeTab === 'embed' ? (
          <div className="h-full w-full relative flex flex-col">
            {iframeLoading && (
              <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-white/90 p-4">
                <RefreshCw size={24} className="animate-spin text-emerald-600 mb-2" />
                <p className="text-xs font-semibold text-slate-600">Đang tải trang web...</p>
                <p className="text-[11px] text-slate-400 mt-1">{source.domain}</p>
              </div>
            )}

            {iframeBlocked ? (
              <div className="p-5 flex flex-col items-center justify-center text-center h-full">
                <div className="grid h-12 w-12 place-items-center rounded-2xl bg-amber-100 text-amber-800 mb-3">
                  <AlertTriangle size={22} />
                </div>
                <h3 className="text-sm font-bold text-slate-900">Không thể nhúng trực tiếp</h3>
                <p className="mt-1.5 text-xs text-slate-600 leading-5 max-w-[280px]">
                  Website <strong>{source.domain}</strong> áp dụng chính sách bảo mật chống nhúng (X-Frame-Options / CSP).
                </p>
                <div className="mt-4 flex gap-2">
                  <button
                    type="button"
                    onClick={() => setActiveTab('info')}
                    className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 shadow-xs"
                  >
                    Xem tóm tắt nguồn
                  </button>
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-xl bg-brand-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-800 shadow-xs"
                  >
                    <ExternalLink size={13} />
                    Mở tab mới
                  </a>
                </div>
              </div>
            ) : (
              <iframe
                key={`${source.url}-${reloadKey}`}
                src={source.url}
                title={`Preview ${source.name}`}
                className="w-full h-full border-0 flex-1 bg-white"
                sandbox="allow-scripts allow-same-origin allow-popups allow-forms"
                onLoad={() => setIframeLoading(false)}
                onError={() => {
                  setIframeLoading(false);
                  setIframeBlocked(true);
                }}
              />
            )}
          </div>
        ) : (
          /* Rich Information / Metadata fallback card */
          <div className="p-4 sm:p-5 space-y-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm space-y-3">
              <div className="flex items-center gap-2">
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-emerald-50 text-emerald-700">
                  <ShieldCheck size={20} />
                </span>
                <div>
                  <h3 className="text-sm font-bold text-slate-950">{source.name}</h3>
                  <p className="text-xs text-emerald-700 font-medium">Nguồn thể thao đã xác thực</p>
                </div>
              </div>

              <div className="space-y-2 pt-2 border-t border-slate-100 text-xs">
                {source.domain && (
                  <div className="flex justify-between items-center py-1">
                    <span className="text-slate-500">Tên miền:</span>
                    <span className="font-semibold text-slate-800">{source.domain}</span>
                  </div>
                )}
                {source.collectedAt && (
                  <div className="flex justify-between items-center py-1">
                    <span className="text-slate-500">Thời điểm cập nhật:</span>
                    <span className="font-medium text-slate-700">{source.collectedAt}</span>
                  </div>
                )}
                <div className="flex justify-between items-center py-1">
                  <span className="text-slate-500">Loại nguồn:</span>
                  <span className="font-medium text-slate-700">
                    {source.isInternal ? 'Cơ sở dữ liệu nội bộ SportHub' : 'Trang tin tức thể thao uy tín'}
                  </span>
                </div>
              </div>

              {source.url && (
                <div className="pt-2">
                  <p className="text-[11px] font-semibold text-slate-500 mb-1">Đường dẫn đầy đủ:</p>
                  <p className="text-xs text-brand-700 break-all bg-slate-50 p-2 rounded-xl border border-slate-200 font-mono">
                    {source.url}
                  </p>
                </div>
              )}
            </div>

            {/* Note banner */}
            <div className="rounded-2xl border border-brand-100 bg-brand-50/60 p-3.5 text-xs text-brand-900">
              <p className="font-semibold mb-1">ℹ️ Về nguồn dữ liệu</p>
              <p className="text-slate-600 leading-relaxed text-[11.5px]">
                SportHub AI đối soát và trích dẫn thông tin từ các cơ quan thể thao chính thống và trang tin tức uy tín để đảm bảo tính chuẩn xác cho câu trả lời.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* 3. Footer */}
      <footer className="flex items-center justify-between border-t border-slate-100 bg-white p-3 sm:px-4 gap-2 shrink-0">
        <button
          type="button"
          onClick={handleCopyUrl}
          disabled={!hasValidUrl}
          className={`inline-flex items-center justify-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-semibold transition-all shadow-xs ${
            copied
              ? 'border-emerald-300 bg-emerald-50 text-emerald-800'
              : hasValidUrl
                ? 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50 hover:text-slate-900'
                : 'border-slate-200 bg-slate-50 text-slate-400 cursor-not-allowed'
          }`}
          title={hasValidUrl ? 'Sao chép đường dẫn URL' : 'Nguồn nội bộ không có URL'}
        >
          {copied ? (
            <>
              <Check size={14} className="text-emerald-700" />
              <span>Đã copy!</span>
            </>
          ) : (
            <>
              <Copy size={14} />
              <span>Copy URL</span>
            </>
          )}
        </button>

        {hasValidUrl ? (
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-brand-700 px-3.5 py-2 text-xs font-semibold text-white shadow-xs hover:bg-brand-800 transition shrink-0 whitespace-nowrap"
          >
            <span>Mở link</span>
            <ExternalLink size={14} />
          </a>
        ) : (
          <span className="text-[11px] text-slate-400 italic">Nguồn nội bộ</span>
        )}
      </footer>
    </aside>
  );
}
