import {
  AlertCircle,
  Bot,
  Briefcase,
  CalendarDays,
  Check,
  ChevronRight,
  Clock3,
  ExternalLink,
  Globe,
  MapPin,
  Mic,
  MicOff,
  Plus,
  Send,
  ShieldCheck,
  Sparkles,
  Star,
  UserRound,
  Volume2,
  VolumeX,
  WalletCards,
  X,
} from 'lucide-react';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Badge, Button } from '@/components/common';
import { WebSourcePreviewPanel } from '@/components/ai/WebSourcePreviewPanel';
import { useSpeechRecognition } from '@/hooks/useSpeechRecognition';
import { useSpeechSynthesis } from '@/hooks/useSpeechSynthesis';
import { parseCitationsFromText, type SourceCitation } from '@/utils/sourceCitationParser';
import {
  AssistantApiError,
  AssistantTimeoutError,
  askSportHubAssistant,
  getAIConversation,
  type AssistantIntent,
  type AssistantMode,
  type AssistantResponse,
  type AssistantSuggestion,
  type AssistantVenueResult,
} from '@/services/aiAssistantService';

const quickPromptsByMode: Record<AssistantMode, string[]> = {
  NATURAL: [
    'Tối nay còn sân cầu lông nào?',
    'Messi hiện thi đấu cho CLB nào?',
    'Sân pickleball ở Thủ Đức ngày mai',
    'Tìm sân bóng dưới 700.000đ',
  ],
  PROFESSIONAL: [
    'Tìm sân bóng dưới 700.000đ',
    'Tối nay còn sân cầu lông nào?',
    'Làm sao để trở thành chủ sân?',
    'Chính sách thanh toán và cọc sân',
  ],
};

type AssistantUiStatus = 'SUCCESS' | 'NEED_MORE_DATA' | 'NO_RESULT' | 'NO_AVAILABLE_SLOT' | 'OUT_OF_SCOPE' | 'ERROR';
type QuickAction = { label: string; kind: 'prefill' | 'link'; value: string };
type Message = {
  id: number;
  role: 'assistant' | 'user';
  text: string;
  suggestions?: AssistantSuggestion[];
  venueResults?: AssistantVenueResult[];
  classification?: 'IN_SCOPE' | 'OUT_OF_SCOPE' | 'UNCLEAR';
  intent?: AssistantIntent;
  retryText?: string;
  uiStatus?: AssistantUiStatus;
  quickActions?: QuickAction[];
};

const clearInteractiveContent = (message: Message): Message => ({
  ...message,
  suggestions: undefined,
  venueResults: undefined,
  retryText: undefined,
  quickActions: undefined,
});

const quickActionsForResponse = (response: AssistantResponse): QuickAction[] | undefined => {
  if (response.action) return [{ label: response.action.label, kind: 'link', value: response.action.route }];
  if (response.status !== 'NO_RESULT') return undefined;
  const sport = response.entities?.sport_type ? ` ${response.entities.sport_type}` : '';
  const location = response.entities?.location ? ` ${response.entities.location}` : '';
  return [
    { label: 'Tìm khu vực khác', kind: 'prefill', value: `Tìm sân${sport} ở ` },
    { label: 'Xem tất cả cơ sở', kind: 'link', value: '/venues' },
    { label: 'Đổi môn thể thao', kind: 'prefill', value: `Tìm sân ở${location} cho môn ` },
  ];
};

const createDefaultWelcomeMessage = (courtId?: number, mode: AssistantMode = 'NATURAL'): Message => ({
  id: 1,
  role: 'assistant',
  text: courtId
    ? 'Chào bạn! Mình đã nhận thông tin sân bạn đang xem. Bạn muốn kiểm tra lịch trống vào ngày nào, hoặc cần tư vấn thêm gì về sân này?'
    : mode === 'PROFESSIONAL'
      ? 'Chào bạn! Tôi là Trợ lý Nghiệp vụ SportHub. Tôi có thể hỗ trợ bạn tìm sân, kiểm tra lịch trống, giá thuê, quy trình đặt sân, thanh toán và chính sách hệ thống.'
      : 'Chào bạn! Mình là Trợ lý AI SportHub. Mình có thể tìm sân & lịch trống theo thời gian thực, đồng thời trò chuyện và giải đáp kiến thức thể thao. Bạn cần hỗ trợ gì hôm nay?',
});

const money = (value: number) => `${value.toLocaleString('vi-VN')}đ`;
const dateLabel = (value: string) =>
  new Intl.DateTimeFormat('vi-VN', { weekday: 'short', day: '2-digit', month: '2-digit' }).format(
    new Date(`${value}T00:00:00`)
  );

export function AIAssistantPage() {
  const [searchParams] = useSearchParams();
  const initialCourtId = Number(searchParams.get('courtId') || searchParams.get('field_id')) || undefined;
  const [conversationId, setConversationId] = useState<string | undefined>(() => {
    return searchParams.get('conversation_id') || localStorage.getItem('sporthub_ai_conversation_id') || undefined;
  });
  const [assistantMode, setAssistantMode] = useState<AssistantMode>(() => {
    const modeParam = searchParams.get('mode')?.toUpperCase();
    if (modeParam === 'PROFESSIONAL' || modeParam === 'NATURAL') return modeParam as AssistantMode;
    const stored = localStorage.getItem('sporthub_ai_assistant_mode')?.toUpperCase();
    if (stored === 'PROFESSIONAL' || stored === 'NATURAL') return stored as AssistantMode;
    return 'NATURAL';
  });
  const [messages, setMessages] = useState<Message[]>([createDefaultWelcomeMessage(initialCourtId, assistantMode)]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingText, setLoadingText] = useState('Đang tìm sân phù hợp...');
  const [contextFieldId, setContextFieldId] = useState<number | undefined>(initialCourtId);
  const [searchContext, setSearchContext] = useState<Record<string, unknown>>({});
  const [selectedSource, setSelectedSource] = useState<SourceCitation | null>(null);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const messagesRef = useRef<HTMLDivElement>(null);
  const queryRef = useRef<HTMLTextAreaElement>(null);
  const requestRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);
  const baseTextRef = useRef('');

  const handleSelectSource = (citation: SourceCitation) => {
    setSelectedSource(citation);
    setIsPreviewOpen(true);
  };

  const handleClosePreview = () => {
    setIsPreviewOpen(false);
  };

  const isListeningRef = useRef(false);

  const {
    isListening,
    isSupported,
    errorMessage: voiceError,
    toggleListening,
    stopListening,
    resetTranscript,
    clearError: clearVoiceError,
  } = useSpeechRecognition({
    lang: 'vi-VN',
    continuous: true,
    interimResults: true,
    onTranscriptChange: ({ fullTranscript }) => {
      if (!isListeningRef.current) return;
      const base = baseTextRef.current.trim();
      const updated = base ? `${base} ${fullTranscript}` : fullTranscript;
      setQuery(updated);
    },
  });

  const {
    isSpeaking,
    speakingId,
    isSupported: isTtsSupported,
    speak,
    stop: stopSpeaking,
    toggle: toggleSpeaking,
  } = useSpeechSynthesis({
    lang: 'vi-VN',
  });

  const [speakerEnabled, setSpeakerEnabled] = useState<boolean>(() => {
    const val =
      localStorage.getItem('sporthub_ai_speaker_enabled') ??
      localStorage.getItem('sporthub_ai_auto_speak');
    return val === 'true';
  });

  const speakerEnabledRef = useRef(speakerEnabled);
  useEffect(() => {
    speakerEnabledRef.current = speakerEnabled;
  }, [speakerEnabled]);

  const handleToggleSpeaker = () => {
    setSpeakerEnabled((prev) => {
      const next = !prev;
      localStorage.setItem('sporthub_ai_speaker_enabled', String(next));
      localStorage.setItem('sporthub_ai_auto_speak', String(next));
      if (!next) {
        stopSpeaking();
      }
      return next;
    });
  };

  const handleToggleVoice = () => {
    if (isSpeaking) stopSpeaking();
    if (!isListening) {
      setQuery('');
      baseTextRef.current = '';
      resetTranscript();
      isListeningRef.current = true;
    } else {
      isListeningRef.current = false;
    }
    toggleListening();
  };

  // Restore conversation history from backend on mount or when conversationId is present
  useEffect(() => {
    if (!conversationId) return;
    let active = true;
    const controller = new AbortController();

    const loadConversation = async () => {
      try {
        const data = await getAIConversation(conversationId, controller.signal);
        if (!active) return;
        if (data && data.messages && data.messages.length > 0) {
          const mapped: Message[] = data.messages.map((m) => {
            if (m.role === 'user') {
              return { id: m.id, role: 'user', text: m.content };
            }
            const payload = m.payload;
            return {
              id: m.id,
              role: 'assistant',
              text: m.content,
              suggestions: payload?.suggestions,
              venueResults: payload?.venue_results,
              classification: payload?.classification,
              intent: payload?.intent,
              uiStatus: payload
                ? payload.classification === 'OUT_OF_SCOPE'
                  ? 'OUT_OF_SCOPE'
                  : payload.status === 'OK'
                    ? 'SUCCESS'
                    : payload.status
                : undefined,
              quickActions: payload ? quickActionsForResponse(payload) : undefined,
            };
          });
          setMessages(mapped);
          if (data.context_snapshot) {
            setSearchContext(data.context_snapshot);
          }
        }
      } catch (err) {
        if (!active || (err instanceof DOMException && err.name === 'AbortError')) return;
        console.warn('Could not restore AI conversation:', err);
        localStorage.removeItem('sporthub_ai_conversation_id');
        setConversationId(undefined);
      }
    };

    void loadConversation();

    return () => {
      active = false;
      controller.abort();
    };
  }, [conversationId]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const container = messagesRef.current;
      if (container) container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [messages, loading]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      requestRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    const clear = () => {
      requestRef.current?.abort();
      localStorage.removeItem('sporthub_ai_conversation_id');
      setConversationId(undefined);
      setMessages([createDefaultWelcomeMessage(initialCourtId)]);
      setQuery('');
      setLoading(false);
      setContextFieldId(initialCourtId);
      setSearchContext({});
    };
    window.addEventListener('sporthub-auth-cleared', clear);
    window.addEventListener('sporthub-session-expired', clear);
    return () => {
      window.removeEventListener('sporthub-auth-cleared', clear);
      window.removeEventListener('sporthub-session-expired', clear);
    };
  }, [initialCourtId]);

  const handleModeChange = (newMode: AssistantMode) => {
    if (newMode === assistantMode) return;
    setAssistantMode(newMode);
    localStorage.setItem('sporthub_ai_assistant_mode', newMode);
  };

  const startNewConversation = () => {
    stopSpeaking();
    if (isListening) stopListening();
    resetTranscript();
    baseTextRef.current = '';
    requestRef.current?.abort();
    localStorage.removeItem('sporthub_ai_conversation_id');
    setConversationId(undefined);
    setMessages([createDefaultWelcomeMessage(initialCourtId, assistantMode)]);
    setSearchContext({});
    setContextFieldId(initialCourtId);
    setSelectedSource(null);
    setIsPreviewOpen(false);
    setQuery('');
    setLoading(false);
  };

  const ask = async (value = query) => {
    stopSpeaking();
    isListeningRef.current = false;
    if (isListening) stopListening();
    resetTranscript();
    baseTextRef.current = '';
    const text = value.trim();
    if (!text || loading) return;
    setQuery('');
    setMessages((current) => [...current.map(clearInteractiveContent), { id: Date.now(), role: 'user', text }]);
    const location = text.match(/(?:ở|tại|quanh)\s+(.+?)(?:\s+(?:có|còn|không)|[?.!,]|$)/i)?.[1]?.trim();
    const partnerRequest = /chủ sân|đối tác|hồ sơ/i.test(text);
    setLoadingText(
      partnerRequest
        ? 'Đang kiểm tra hồ sơ đối tác...'
        : location
          ? `Đang tìm sân ở ${location}...`
          : 'Đang tìm sân phù hợp...'
    );
    setLoading(true);
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    try {
      const response = await askSportHubAssistant(
        text,
        contextFieldId,
        searchContext,
        conversationId,
        controller.signal,
        assistantMode
      );
      if (!mountedRef.current || controller.signal.aborted) return;

      if (response.conversation_id) {
        setConversationId(response.conversation_id);
        localStorage.setItem('sporthub_ai_conversation_id', response.conversation_id);
      }

      if (response.assistant_mode) {
        setAssistantMode(response.assistant_mode);
      }

      if (response.classification === 'OUT_OF_SCOPE') {
        setSearchContext({});
        setContextFieldId(undefined);
      } else {
        setSearchContext(response.understood);
        if (response.suggestions[0]) setContextFieldId(response.suggestions[0].field_id);
        else if (response.venue_results[0]) setContextFieldId(response.venue_results[0].field_id);
        else if (response.context_reset) setContextFieldId(undefined);
      }
      const messageId = Date.now() + 1;
      setMessages((current) => [
        ...current.map(clearInteractiveContent),
        {
          id: messageId,
          role: 'assistant',
          text: response.reply,
          suggestions: response.suggestions,
          venueResults: response.venue_results,
          classification: response.classification,
          intent: response.intent,
          uiStatus:
            response.classification === 'OUT_OF_SCOPE'
              ? 'OUT_OF_SCOPE'
              : response.status === 'OK'
                ? 'SUCCESS'
                : response.status,
          quickActions: quickActionsForResponse(response),
        },
      ]);

      // If citations exist and preview panel is open, update selected source to the first citation
      const { citations } = parseCitationsFromText(response.reply);
      if (citations.length > 0 && isPreviewOpen) {
        setSelectedSource(citations[0]);
      }

      if (speakerEnabledRef.current && response.reply) {
        speak(response.reply, messageId);
      }
    } catch (error) {
      if (!mountedRef.current || controller.signal.aborted || (error instanceof DOMException && error.name === 'AbortError'))
        return;
      const errorText =
        error instanceof AssistantTimeoutError
          ? 'SportHub phản hồi quá lâu. Yêu cầu đã được dừng sau 12 giây, vui lòng thử lại.'
          : error instanceof AssistantApiError
            ? error.message
            : 'Không thể kết nối backend SportHub. Hãy kiểm tra backend đang chạy tại cổng 8000 rồi thử lại.';
      setMessages((current) => [
        ...current.map(clearInteractiveContent),
        { id: Date.now() + 1, role: 'assistant', text: errorText, retryText: text, uiStatus: 'ERROR' },
      ]);
    } finally {
      if (mountedRef.current && requestRef.current === controller) {
        requestRef.current = null;
        setLoading(false);
      }
    }
  };

  const applyQuickAction = (value: string) => {
    stopSpeaking();
    if (isListening) stopListening();
    setQuery(value);
    window.requestAnimationFrame(() => queryRef.current?.focus());
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    stopSpeaking();
    if (isListening) stopListening();
    void ask();
  };

  return (
    <div className="h-[calc(100dvh-4rem)] min-h-[520px] bg-[radial-gradient(circle_at_top_left,_#ecfdf5,_transparent_35%),#f8fafc] p-2 sm:p-4 lg:p-5 overflow-hidden">
      <div
        className={`mx-auto grid h-full max-w-7xl gap-3 sm:gap-4 transition-all duration-200 ${
          isPreviewOpen
            ? 'lg:grid-cols-[minmax(0,1fr)_340px] xl:grid-cols-[240px_minmax(0,1fr)_360px] 2xl:grid-cols-[260px_minmax(0,1fr)_380px]'
            : 'lg:grid-cols-[260px_minmax(0,1fr)] xl:grid-cols-[280px_minmax(0,1fr)]'
        }`}
      >
        <aside
          className={`rounded-3xl bg-brand-900 p-4 xl:p-5 text-white shadow-xl flex-col justify-between h-full overflow-y-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden ${
            isPreviewOpen ? 'hidden xl:flex' : 'hidden lg:flex'
          }`}
        >
          <div>
            <div className="grid h-10 w-10 place-items-center rounded-2xl bg-brand-500 shadow-md">
              <Sparkles size={20} />
            </div>
            <h1 className="mt-3 text-lg xl:text-xl font-extrabold text-white">Trợ lý SportHub</h1>
            <p className="mt-1 text-xs leading-5 text-slate-300 min-h-[36px]">
              {assistantMode === 'NATURAL'
                ? 'Hội thoại tự nhiên & kiến thức 6 môn thể thao chuyên sâu.'
                : 'Trợ lý nghiệp vụ chính xác, hỗ trợ vận hành & đặt sân.'}
            </p>

            <div className="mt-3 space-y-2">
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Chế độ hoạt động</p>
              <div className="space-y-2">
                <button
                  type="button"
                  onClick={() => handleModeChange('NATURAL')}
                  className={`group w-full rounded-2xl border p-2.5 text-left transition-all ${
                    assistantMode === 'NATURAL'
                      ? 'border-emerald-400/80 bg-white/15 text-white shadow-lg ring-1 ring-emerald-400/60'
                      : 'border-white/10 bg-white/5 text-slate-300 hover:border-white/20 hover:bg-white/10'
                  }`}
                >
                  <div className="flex items-center justify-between gap-1.5">
                    <span className="flex items-center gap-1.5 text-xs font-bold text-white whitespace-nowrap min-w-0">
                      <span className="text-sm">🌿</span> <span>Tự nhiên</span>
                    </span>
                    {assistantMode === 'NATURAL' ? (
                      <span className="flex items-center gap-1 rounded-full bg-emerald-400/20 px-2 py-0.5 text-[10px] font-bold text-emerald-300 whitespace-nowrap shrink-0">
                        <Check size={10} strokeWidth={3} /> Đang chọn
                      </span>
                    ) : (
                      <span className="text-[10px] font-medium text-slate-400 group-hover:text-slate-200 whitespace-nowrap shrink-0">Chọn</span>
                    )}
                  </div>
                  <p className="mt-1 text-[11px] font-semibold text-emerald-200/90 truncate">SportHub + Kiến thức thể thao</p>
                  <p className="mt-0.5 text-[10.5px] leading-4 text-slate-300/80 line-clamp-2">
                    Hội thoại tự nhiên, thân thiện & giải đáp 6 môn thể thao hỗ trợ
                  </p>
                </button>

                <button
                  type="button"
                  onClick={() => handleModeChange('PROFESSIONAL')}
                  className={`group w-full rounded-2xl border p-2.5 text-left transition-all ${
                    assistantMode === 'PROFESSIONAL'
                      ? 'border-brand-400/80 bg-white/15 text-white shadow-lg ring-1 ring-brand-400/60'
                      : 'border-white/10 bg-white/5 text-slate-300 hover:border-white/20 hover:bg-white/10'
                  }`}
                >
                  <div className="flex items-center justify-between gap-1.5">
                    <span className="flex items-center gap-1.5 text-xs font-bold text-white whitespace-nowrap min-w-0">
                      <Briefcase size={13} className="text-brand-300 shrink-0" /> <span>Chuyên nghiệp</span>
                    </span>
                    {assistantMode === 'PROFESSIONAL' ? (
                      <span className="flex items-center gap-1 rounded-full bg-brand-400/20 px-2 py-0.5 text-[10px] font-bold text-brand-300 whitespace-nowrap shrink-0">
                        <Check size={10} strokeWidth={3} /> Đang chọn
                      </span>
                    ) : (
                      <span className="text-[10px] font-medium text-slate-400 group-hover:text-slate-200 whitespace-nowrap shrink-0">Chọn</span>
                    )}
                  </div>
                  <p className="mt-1 text-[11px] font-semibold text-brand-200/90 truncate">Trợ lý nghiệp vụ SportHub</p>
                  <p className="mt-0.5 text-[10.5px] leading-4 text-slate-300/80 line-clamp-2">
                    Tập trung tìm sân, giá, lịch trống & quy trình đặt sân
                  </p>
                </button>
              </div>
            </div>
          </div>

          <div className="mt-3 pt-1 space-y-2.5">
            <div className="space-y-1.5 text-xs text-slate-300">
              <p className="flex items-center gap-2.5">
                <CalendarDays className="text-brand-400 shrink-0" size={14} /> Tìm theo ngày và giờ trống
              </p>
              <p className="flex items-center gap-2.5">
                <MapPin className="text-brand-400 shrink-0" size={14} /> Lọc khu vực và bán kính
              </p>
              <p className="flex items-center gap-2.5">
                <WalletCards className="text-brand-400 shrink-0" size={14} /> So khớp giá và ngân sách
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/5 p-2.5 text-xs leading-5 text-slate-400 flex flex-col justify-center">
              <ShieldCheck className="mb-0.5 text-brand-400 shrink-0" size={15} />
              <p className="line-clamp-2 text-[11px] leading-4">
                {assistantMode === 'NATURAL'
                  ? 'SportHub AI hỗ trợ nghiệp vụ và kiến thức 6 môn thể thao.'
                  : 'Chế độ Chuyên nghiệp tập trung giải quyết nghiệp vụ SportHub.'}
              </p>
            </div>
          </div>
        </aside>

        <section className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card sm:rounded-3xl">
          <header className="flex flex-col gap-2.5 border-b border-slate-100 bg-white px-4 py-3 sm:px-6">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
              {/* Top Row on Mobile / Left Side on Desktop: AI icon + Title + Subtitle + Mobile New Chat button */}
              <div className="flex items-center justify-between gap-2 min-w-0">
                <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
                  <span className="relative grid h-9 w-9 sm:h-11 sm:w-11 shrink-0 place-items-center rounded-2xl bg-ai-500 text-white shadow-sm">
                    <Bot size={20} className="sm:hidden" />
                    <Bot size={22} className="hidden sm:block" />
                    <i className="absolute bottom-0 right-0 h-2.5 w-2.5 sm:h-3 sm:w-3 rounded-full border-2 border-white bg-emerald-400" />
                  </span>
                  <div className="min-w-0">
                    <h1 className="text-sm sm:text-lg font-bold text-slate-950 truncate">
                      AI Trợ lý SportHub
                    </h1>
                    <p className="text-[11px] sm:text-xs text-slate-500 truncate">
                      Dữ liệu thời gian thực + Kiến thức thể thao
                    </p>
                  </div>
                </div>

                {/* Mobile New Chat Button */}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={startNewConversation}
                  className="sm:hidden text-xs font-medium text-slate-600 hover:text-brand-700 h-8 px-2.5 shrink-0 whitespace-nowrap inline-flex items-center gap-1 border-slate-200 shadow-2xs"
                  title="Bắt đầu cuộc trò chuyện mới"
                >
                  <Plus size={14} />
                  <span className="text-[11px] font-semibold">Chat mới</span>
                </Button>
              </div>

              {/* Bottom Row on Mobile / Right Side on Desktop: Mode Switch + Speaker + Desktop New Chat */}
              <div className="flex items-center gap-1.5 sm:gap-2 justify-between sm:justify-end sm:ml-auto shrink-0 w-full sm:w-auto">
                {/* 1 & 2: Mode Segmented Control (Tự nhiên & Chuyên nghiệp) */}
                <div
                  role="radiogroup"
                  aria-label="Chế độ trợ lý AI"
                  className="flex-1 sm:flex-initial inline-flex items-center rounded-xl bg-slate-100 p-0.5 sm:p-1 border border-slate-200/80 shadow-inner h-8 shrink-0"
                >
                  <button
                    type="button"
                    role="radio"
                    aria-checked={assistantMode === 'NATURAL'}
                    onClick={() => handleModeChange('NATURAL')}
                    className={`flex-1 sm:flex-initial flex items-center justify-center gap-1 rounded-lg px-2 sm:px-2.5 py-0.5 text-[11px] sm:text-xs font-semibold transition-all h-7 sm:h-6 ${
                      assistantMode === 'NATURAL'
                        ? 'bg-white text-emerald-800 shadow-xs ring-1 ring-slate-200/80'
                        : 'text-slate-600 hover:text-slate-900 hover:bg-white/50'
                    }`}
                    title="Chế độ Tự nhiên: SportHub + kiến thức 6 môn thể thao"
                  >
                    <span>🌿</span>
                    <span>Tự nhiên</span>
                  </button>
                  <button
                    type="button"
                    role="radio"
                    aria-checked={assistantMode === 'PROFESSIONAL'}
                    onClick={() => handleModeChange('PROFESSIONAL')}
                    className={`flex-1 sm:flex-initial flex items-center justify-center gap-1 rounded-lg px-2 sm:px-2.5 py-0.5 text-[11px] sm:text-xs font-semibold transition-all h-7 sm:h-6 ${
                      assistantMode === 'PROFESSIONAL'
                        ? 'bg-white text-brand-900 shadow-xs ring-1 ring-slate-200/80'
                        : 'text-slate-600 hover:text-slate-900 hover:bg-white/50'
                    }`}
                    title="Chế độ Chuyên nghiệp: Nghiệp vụ SportHub & hỗ trợ hệ thống"
                  >
                    <span>💼</span>
                    <span>Chuyên nghiệp</span>
                  </button>
                </div>

                {/* 3: Speaker Control (Đọc: Bật / Đọc: Tắt) */}
                {isTtsSupported && (
                  <button
                    type="button"
                    onClick={handleToggleSpeaker}
                    aria-pressed={speakerEnabled}
                    className={`inline-flex items-center justify-center gap-1.5 rounded-xl px-2.5 py-1 text-xs font-semibold transition-all border h-8 shrink-0 whitespace-nowrap shadow-xs ${
                      speakerEnabled
                        ? 'bg-emerald-50 text-emerald-800 border-emerald-300 hover:bg-emerald-100'
                        : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50 hover:text-slate-900'
                    }`}
                    title={
                      speakerEnabled
                        ? 'Tự động đọc câu trả lời: Đang BẬT (Bấm để tắt)'
                        : 'Tự động đọc câu trả lời: Đang TẮT (Bấm để bật)'
                    }
                  >
                    {speakerEnabled ? (
                      <>
                        <Volume2 size={14} className="text-emerald-700 shrink-0" />
                        <span className="text-[11px] sm:text-xs">Đọc: Bật</span>
                      </>
                    ) : (
                      <>
                        <VolumeX size={14} className="text-slate-400 shrink-0" />
                        <span className="text-[11px] sm:text-xs">Đọc: Tắt</span>
                      </>
                    )}
                  </button>
                )}

                {/* 4: Desktop Đoạn chat mới button */}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={startNewConversation}
                  className="hidden sm:inline-flex text-xs font-medium text-slate-600 hover:text-brand-700 h-8 px-2.5 shrink-0 whitespace-nowrap"
                  title="Bắt đầu cuộc trò chuyện mới"
                >
                  <Plus size={14} className="mr-1" />
                  <span>Đoạn chat mới</span>
                </Button>
              </div>
            </div>

            {/* Scope hint sub-bar */}
            <div className="flex items-center justify-between rounded-xl bg-slate-50/80 px-2.5 sm:px-3 py-1.5 text-[11px] sm:text-xs text-slate-600 border border-slate-100">
              <div className="flex items-center gap-1.5 min-w-0">
                <span className="font-semibold text-slate-500 shrink-0">Phạm vi:</span>
                {assistantMode === 'NATURAL' ? (
                  <span className="text-emerald-800 font-medium truncate">
                    SportHub + 6 môn thể thao (Bóng đá, Cầu lông, Pickleball, Tennis, Bóng rổ, Bóng chuyền)
                  </span>
                ) : (
                  <span className="text-brand-800 font-medium truncate">
                    Nghiệp vụ SportHub (Tìm sân, Giá, Lịch trống, Đặt sân, Thanh toán, Đối tác)
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0 ml-2">
                <span className="text-[11px] text-slate-400 hidden lg:inline">
                  {assistantMode === 'NATURAL' ? 'Hội thoại tự nhiên' : 'Chính xác & trực tiếp'}
                </span>
              </div>
            </div>
          </header>

          <div ref={messagesRef} className="min-h-0 flex-1 space-y-4 sm:space-y-5 overflow-y-auto bg-slate-50/60 p-3 sm:p-6">
            {messages.map((message) => {
              const parsedCitations =
                message.role === 'assistant' ? parseCitationsFromText(message.text) : { citations: [] };

              return (
                <div
                  key={message.id}
                  className={`flex items-start gap-2.5 ${message.role === 'user' ? 'justify-end' : ''}`}
                >
                  {message.role === 'assistant' && (
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-brand-600 text-white">
                      <Bot size={16} />
                    </span>
                  )}
                  <div className={`min-w-0 max-w-[94%] sm:max-w-[88%] ${message.role === 'user' ? 'order-first' : ''}`}>
                    <div
                      className={`rounded-2xl px-4 py-3 text-sm leading-6 break-words whitespace-pre-wrap ${
                        message.role === 'user'
                          ? 'rounded-tr-md bg-brand-800 text-white'
                          : 'rounded-tl-md border border-slate-200 bg-white text-slate-700 shadow-sm'
                      }`}
                    >
                      {message.role === 'assistant' ? parsedCitations.bodyText : message.text}
                    </div>

                    {/* Source citations chips if message contains sources */}
                    {message.role === 'assistant' && parsedCitations.citations.length > 0 && (
                      <div className="mt-2 flex flex-wrap items-center gap-1.5 pt-0.5">
                        <span className="text-[10.5px] font-bold uppercase tracking-wider text-slate-400 mr-0.5 flex items-center gap-1">
                          <Globe size={11} className="text-emerald-600" />
                          Nguồn:
                        </span>
                        {parsedCitations.citations.map((cit) => {
                          const isCurrentActive =
                            isPreviewOpen &&
                            selectedSource?.name === cit.name &&
                            selectedSource?.url === cit.url;
                          return (
                            <button
                              key={cit.id}
                              type="button"
                              onClick={() => handleSelectSource(cit)}
                              className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] font-semibold transition-all border shadow-2xs ${
                                isCurrentActive
                                  ? 'bg-emerald-100 text-emerald-900 border-emerald-400 ring-2 ring-emerald-300'
                                  : 'bg-white text-slate-700 border-slate-200 hover:border-emerald-300 hover:bg-emerald-50/70 hover:text-emerald-900'
                              }`}
                              title={`Xem preview nguồn: ${cit.name}${cit.domain ? ` (${cit.domain})` : ''}`}
                            >
                              <Globe size={11} className={isCurrentActive ? 'text-emerald-700' : 'text-slate-400'} />
                              <span className="truncate max-w-[130px] sm:max-w-[170px] font-medium">{cit.name}</span>
                              {cit.domain && (
                                <span className="text-[10px] text-slate-400 font-normal">· {cit.domain}</span>
                              )}
                            </button>
                          );
                        })}
                      </div>
                    )}

                    {message.retryText && (
                      <Button
                        className="mt-2"
                        size="sm"
                        variant="outline"
                        onClick={() => void ask(message.retryText)}
                      >
                        Thử lại
                      </Button>
                    )}
                    {message.role === 'assistant' && (
                      <div className="mt-1.5 flex flex-wrap items-center gap-2">
                        {isTtsSupported && message.text && (
                          (() => {
                            const isCurrentSpeaking =
                              isSpeaking &&
                              speakingId !== null &&
                              String(speakingId) === String(message.id);

                            return (
                              <div className="relative group/tts inline-flex">
                                <button
                                  type="button"
                                  onClick={() => toggleSpeaking(message.text, message.id)}
                                  className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold transition-all border shadow-xs ${
                                    isCurrentSpeaking
                                      ? 'bg-amber-50 text-amber-900 border-amber-300 ring-2 ring-amber-200 animate-pulse'
                                      : 'bg-slate-50/80 text-slate-600 border-slate-200 hover:bg-slate-100 hover:text-slate-900'
                                  }`}
                                  aria-label={
                                    isCurrentSpeaking
                                      ? 'Đang đọc câu trả lời (Bấm để dừng)'
                                      : 'Nghe đọc câu trả lời'
                                  }
                                >
                                  {isCurrentSpeaking ? (
                                    <>
                                      <Volume2 size={13} className="text-amber-700 shrink-0 animate-bounce" />
                                      <span className="text-[11px] font-bold text-amber-900">Đang đọc...</span>
                                    </>
                                  ) : (
                                    <>
                                      <Volume2 size={13} className="shrink-0 text-slate-500" />
                                      <span className="text-[11px] font-medium">Nghe đọc</span>
                                    </>
                                  )}
                                </button>
                                <div className="pointer-events-none absolute left-0 bottom-full mb-1.5 z-30 opacity-0 group-hover/tts:opacity-100 transition-all duration-150 transform scale-95 group-hover/tts:scale-100 whitespace-nowrap rounded-lg bg-slate-900/95 backdrop-blur-xs px-2.5 py-1 text-[11px] font-medium text-white shadow-lg border border-slate-700/60">
                                  {isCurrentSpeaking
                                    ? 'Dừng đọc câu trả lời'
                                    : 'Đọc câu trả lời bằng giọng nói (vi-VN)'}
                                </div>
                              </div>
                            );
                          })()
                        )}
                        {message.classification && message.classification !== 'IN_SCOPE' && (
                          <span className="text-[11px] font-semibold text-slate-400">
                            {message.classification === 'OUT_OF_SCOPE'
                              ? 'Ngoài phạm vi SportHub AI'
                              : 'Cần làm rõ yêu cầu SportHub'}
                          </span>
                        )}
                      </div>
                    )}
                    {!!message.suggestions?.length && (
                      <div className="mt-3 grid gap-3 xl:grid-cols-2">
                        {message.suggestions.map((item) => (
                          <SuggestionCard key={`${item.field_id}-${item.time_slot_id}`} item={item} />
                        ))}
                      </div>
                    )}
                    {!!message.venueResults?.length && (
                      <div className="mt-3 grid gap-3 xl:grid-cols-2">
                        {message.venueResults.map((item) => (
                          <VenueResultCard key={item.field_id} item={item} />
                        ))}
                      </div>
                    )}
                    <QuickActions actions={message.quickActions} onPrefill={applyQuickAction} />
                  </div>
                  {message.role === 'user' && (
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-slate-200 text-slate-600">
                      <UserRound size={16} />
                    </span>
                  )}
                </div>
              );
            })}
            {loading && (
              <div className="flex items-center gap-2.5">
                <span className="grid h-8 w-8 place-items-center rounded-xl bg-brand-600 text-white">
                  <Bot size={16} />
                </span>
                <div className="flex items-center gap-2 rounded-2xl rounded-tl-md border bg-white px-4 py-3 text-sm text-slate-500">
                  <span>{loadingText}</span>
                  <span className="flex gap-1">
                    <i className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400" />
                    <i className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:120ms]" />
                    <i className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:240ms]" />
                  </span>
                </div>
              </div>
            )}
          </div>

          <footer className="border-t border-slate-100 bg-white p-3 sm:p-5">
            {voiceError && (
              <div className="mb-3 flex items-center justify-between gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-2 text-xs text-amber-800 animate-in fade-in duration-200">
                <div className="flex items-center gap-2 min-w-0">
                  <AlertCircle size={15} className="shrink-0 text-amber-600" />
                  <span className="truncate sm:whitespace-normal">{voiceError}</span>
                </div>
                <button
                  type="button"
                  onClick={clearVoiceError}
                  className="shrink-0 rounded p-1 text-amber-600 hover:bg-amber-100 hover:text-amber-900"
                  aria-label="Đóng thông báo lỗi"
                  title="Đóng"
                >
                  <X size={14} />
                </button>
              </div>
            )}

            {isListening && (
              <div className="mb-3 flex items-center justify-between rounded-xl border border-red-200 bg-red-50/90 px-3.5 py-2 text-xs text-red-700 animate-pulse">
                <div className="flex items-center gap-2">
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
                    <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-red-500" />
                  </span>
                  <span className="font-medium">Đang nghe tiếng Việt (vi-VN)... Hãy nói câu hỏi của bạn.</span>
                </div>
                <button
                  type="button"
                  onClick={stopListening}
                  className="font-semibold text-red-800 underline hover:text-red-950"
                >
                  Dừng
                </button>
              </div>
            )}

            {messages.length === 1 && (
              <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
                {quickPromptsByMode[assistantMode].map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => void ask(prompt)}
                    className="shrink-0 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 hover:border-brand-300 hover:text-brand-700 shadow-sm transition"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            )}
            <form
              onSubmit={submit}
              className="relative flex items-end gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-2 focus-within:border-brand-400 focus-within:ring-2 focus-within:ring-brand-100"
            >
              <label htmlFor="assistant-query" className="sr-only">
                Nhập yêu cầu tìm sân
              </label>
              <textarea
                ref={queryRef}
                id="assistant-query"
                rows={1}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    if (isListening) stopListening();
                    void ask();
                  }
                }}
                placeholder={isListening ? 'Đang nhận diện giọng nói (bạn có thể chỉnh sửa)...' : 'Ví dụ: Tối nay còn sân cầu lông nào?'}
                className="max-h-28 min-h-10 flex-1 resize-none rounded-xl bg-transparent px-2 py-2 text-sm outline-none focus:outline-none focus-visible:outline-none"
              />
              <div className="group relative shrink-0">
                <Button
                  type="button"
                  size="sm"
                  variant={isListening ? 'danger' : 'outline'}
                  onClick={handleToggleVoice}
                  aria-label={isListening ? 'Dừng nhận diện giọng nói' : 'Nhập bằng giọng nói (Tiếng Việt)'}
                  className={`!h-10 !w-10 shrink-0 !p-0 transition-all ${
                    isListening
                      ? 'bg-red-600 text-white shadow-md shadow-red-200 ring-2 ring-red-400 ring-offset-1 hover:bg-red-700'
                      : 'border-slate-300 text-slate-700 hover:border-brand-400 hover:bg-brand-50 hover:text-brand-700'
                  }`}
                >
                  {isListening ? (
                    <MicOff size={20} strokeWidth={2.2} className="animate-pulse" />
                  ) : (
                    <Mic size={20} strokeWidth={2.2} />
                  )}
                </Button>
                <div className="pointer-events-none absolute -top-9 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-lg bg-slate-900/90 px-2.5 py-1 text-[11px] font-medium text-white opacity-0 shadow-lg transition-opacity duration-150 group-hover:opacity-100 z-20">
                  {!isSupported
                    ? 'Trình duyệt chưa hỗ trợ'
                    : isListening
                      ? 'Dừng nhận diện'
                      : 'Nhập bằng giọng nói (vi-VN)'}
                  <span className="absolute -bottom-1 left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-900/90" />
                </div>
              </div>

              <div className="group relative shrink-0">
                <Button
                  type="submit"
                  size="sm"
                  disabled={!query.trim() || loading}
                  aria-label="Gửi yêu cầu"
                  className="!h-10 !w-10 shrink-0 !p-0"
                >
                  <Send size={18} strokeWidth={2.2} />
                </Button>
                {query.trim() && !loading && (
                  <div className="pointer-events-none absolute -top-9 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-lg bg-slate-900/90 px-2.5 py-1 text-[11px] font-medium text-white opacity-0 shadow-lg transition-opacity duration-150 group-hover:opacity-100 z-20">
                    Gửi yêu cầu
                    <span className="absolute -bottom-1 left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-900/90" />
                  </div>
                )}
              </div>
            </form>
            <p className="mt-2 text-center text-[11px] text-slate-400">
              Chỉ hỗ trợ nghiệp vụ SportHub AI. Dữ liệu cá nhân được giới hạn theo tài khoản và quyền đang đăng nhập.
            </p>
          </footer>
        </section>

        {/* Desktop Web Source Preview Panel (Right Side Column) */}
        {isPreviewOpen && (
          <div className="hidden lg:flex h-full min-h-0 min-w-0 flex-col animate-in fade-in duration-200">
            <WebSourcePreviewPanel
              source={selectedSource}
              onClose={handleClosePreview}
            />
          </div>
        )}
      </div>

      {/* Mobile / Tablet Web Source Preview Slide-over Overlay */}
      {isPreviewOpen && (
        <div
          className="fixed inset-0 z-50 overflow-hidden bg-slate-950/45 backdrop-blur-xs lg:hidden animate-in fade-in duration-200"
          onClick={(e) => {
            if (e.target === e.currentTarget) handleClosePreview();
          }}
        >
          <div className="ml-auto h-[100dvh] w-[min(100%,26rem)] max-w-full bg-white shadow-2xl p-2 sm:p-3 animate-in slide-in-from-right duration-200">
            <WebSourcePreviewPanel
              source={selectedSource}
              onClose={handleClosePreview}
              className="h-full !rounded-2xl"
            />
          </div>
        </div>
      )}
    </div>
  );
}

function QuickActions({ actions, onPrefill }: { actions?: QuickAction[]; onPrefill: (value: string) => void }) {
  if (!actions?.length) return null;
  return (
    <div className="mt-2.5 flex flex-wrap gap-2">
      {actions.map((action) =>
        action.kind === 'link' ? (
          <Link
            key={action.label}
            to={action.value}
            className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-brand-300 hover:text-brand-700"
          >
            {action.label}
          </Link>
        ) : (
          <button
            key={action.label}
            type="button"
            onClick={() => onPrefill(action.value)}
            className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-brand-300 hover:text-brand-700"
          >
            {action.label}
          </button>
        )
      )}
    </div>
  );
}

function VenueResultCard({ item }: { item: AssistantVenueResult }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-bold uppercase tracking-wide text-brand-700">
        {item.sport_type} · {item.court_type}
      </p>
      <h2 className="mt-1 font-bold text-slate-950">{item.facility_name}</h2>
      <p className="text-xs font-medium text-slate-500">Sân: {item.court_name}</p>
      <p className="mt-2 flex items-start gap-1.5 text-xs text-slate-500">
        <MapPin size={14} className="shrink-0" />
        {item.location}
      </p>
      <div className="mt-3 flex items-center justify-between">
        <b className="text-sm text-brand-700">Giá cơ bản từ {money(item.base_price)}</b>
        <span className="text-xs text-amber-700">
          <Star size={12} className="mr-1 inline fill-current" />
          {item.rating.toFixed(1)}
        </span>
      </div>
      <Link className="mt-4 block" to={`/courts/${item.field_id}`}>
        <Button variant="outline" className="w-full">
          Xem sân và chọn lịch
        </Button>
      </Link>
    </article>
  );
}

function SuggestionCard({ item }: { item: AssistantSuggestion }) {
  const slotIds = item.time_slot_ids?.length ? item.time_slot_ids : [item.time_slot_id];
  const slotQuery = slotIds.join(',');
  const rememberSelection = () =>
    sessionStorage.setItem(
      'sporthub_booking_context',
      JSON.stringify({
        venueId: item.facility_id,
        courtId: item.field_id,
        date: item.booking_date,
        slotId: item.time_slot_id,
        slotIds,
        startTime: item.start_time,
        endTime: item.end_time,
        price: item.price,
      })
    );
  return (
    <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-wide text-brand-700">
              {item.sport_type}
              {item.court_type ? ` · ${item.court_type}` : ''}
            </p>
            <h2 className="mt-1 font-bold text-slate-950">{item.facility_name}</h2>
            <p className="mt-0.5 text-xs font-medium text-slate-500">Sân: {item.court_name}</p>
          </div>
          {item.is_nearest_alternative && <Badge variant="warning">Phương án gần nhất</Badge>}
        </div>
        <p className="mt-2 flex items-start gap-1.5 text-xs leading-5 text-slate-500">
          <MapPin size={14} className="mt-0.5 shrink-0" />
          {item.location}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="rounded-lg bg-brand-50 px-2.5 py-1.5 text-xs font-semibold text-brand-700">
            <Clock3 size={13} className="mr-1 inline" />
            {item.selected_slots?.length > 1
              ? `${item.selected_slots.length} khung giờ`
              : `${item.start_time}–${item.end_time}`}{' '}
            · {dateLabel(item.booking_date)}
            {item.duration_minutes ? ` · ${item.duration_minutes} phút` : ''}
          </span>
          <span className="rounded-lg bg-slate-100 px-2.5 py-1.5 text-xs font-bold text-slate-700">
            {money(item.price)}
          </span>
          <span className="rounded-lg bg-amber-50 px-2.5 py-1.5 text-xs font-semibold text-amber-700">
            <Star size={12} className="mr-1 inline fill-current" />
            {item.rating.toFixed(1)}
          </span>
          <Badge variant="success">Còn trống</Badge>
        </div>
        {item.selected_slots?.length > 1 && (
          <p className="mt-2 text-xs text-slate-600">
            {item.selected_slots.map((slot) => `${slot.start_time.slice(0, 5)}–${slot.end_time.slice(0, 5)}`).join(', ')}
          </p>
        )}
        <p className="mt-3 text-xs leading-5 text-slate-500">
          <b>Lý do AI gợi ý:</b> {item.reason}
        </p>
        <div className="mt-4 grid grid-cols-2 gap-2">
          <Link
            to={`/courts/${item.field_id}?date=${item.booking_date}&slot=${item.time_slot_id}&slots=${slotQuery}`}
          >
            <Button variant="outline" className="w-full">
              Xem sân
            </Button>
          </Link>
          <Link
            onClick={rememberSelection}
            to={`/booking/${item.field_id}?date=${item.booking_date}&slot=${item.time_slot_id}&slots=${slotQuery}`}
          >
            <Button className="w-full">
              Tiếp tục đặt <ChevronRight size={15} />
            </Button>
          </Link>
        </div>
      </div>
    </article>
  );
}
