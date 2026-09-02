import { Bot, CalendarDays, ChevronRight, Clock3, MapPin, Send, ShieldCheck, Sparkles, Star, UserRound, WalletCards } from 'lucide-react';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Badge, Button } from '@/components/common';
import { AssistantApiError, AssistantTimeoutError, askSportHubAssistant, type AssistantIntent, type AssistantSuggestion, type AssistantVenueResult } from '@/services/aiAssistantService';

const quickPrompts = [
  'Tối nay còn sân cầu lông nào?',
  'Tìm sân bóng dưới 700.000đ',
  'Sân pickleball ở Thủ Đức ngày mai',
  'Làm sao để trở thành chủ sân?',
];

type AssistantUiStatus = 'SUCCESS' | 'NEED_MORE_DATA' | 'NO_RESULT' | 'NO_AVAILABLE_SLOT' | 'OUT_OF_SCOPE' | 'ERROR';
type QuickAction = { label: string; kind: 'prefill' | 'link'; value: string };
type Message = { id: number; role: 'assistant' | 'user'; text: string; suggestions?: AssistantSuggestion[]; venueResults?: AssistantVenueResult[]; classification?: 'IN_SCOPE' | 'OUT_OF_SCOPE' | 'UNCLEAR'; intent?: AssistantIntent; retryText?: string; uiStatus?: AssistantUiStatus; quickActions?: QuickAction[] };

const clearInteractiveContent = (message: Message): Message => ({
  ...message, suggestions: undefined, venueResults: undefined, retryText: undefined, quickActions: undefined,
});

const quickActionsForResponse = (response: Awaited<ReturnType<typeof askSportHubAssistant>>): QuickAction[] | undefined => {
  if (response.action) return [{ label: response.action.label, kind: 'link', value: response.action.route }];
  if (response.status !== 'NO_RESULT') return undefined;
  const sport = response.entities.sport_type ? ` ${response.entities.sport_type}` : '';
  const location = response.entities.location ? ` ${response.entities.location}` : '';
  return [
    { label: 'Tìm khu vực khác', kind: 'prefill', value: `Tìm sân${sport} ở ` },
    { label: 'Xem tất cả cơ sở', kind: 'link', value: '/venues' },
    { label: 'Đổi môn thể thao', kind: 'prefill', value: `Tìm sân ở${location} cho môn ` },
  ];
};

const money = (value: number) => `${value.toLocaleString('vi-VN')}đ`;
const dateLabel = (value: string) => new Intl.DateTimeFormat('vi-VN', { weekday: 'short', day: '2-digit', month: '2-digit' }).format(new Date(`${value}T00:00:00`));

export function AIAssistantPage() {
  const [searchParams] = useSearchParams();
  const initialCourtId = Number(searchParams.get('courtId') || searchParams.get('field_id')) || undefined;
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 1,
      role: 'assistant',
      text: initialCourtId
        ? 'Chào bạn! Mình đã nhận thông tin sân bạn đang xem. Bạn muốn kiểm tra lịch trống vào ngày nào, hoặc cần tư vấn thêm gì về sân này?'
        : 'Chào bạn! Mình có thể tìm sân và khung giờ còn trống trực tiếp từ hệ thống SportHub. Bạn muốn chơi môn gì, ở đâu và khi nào?',
    },
  ]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingText, setLoadingText] = useState('Đang tìm sân phù hợp...');
  const [contextFieldId, setContextFieldId] = useState<number | undefined>(initialCourtId);
  const [searchContext, setSearchContext] = useState<Record<string, unknown>>({});
  const messagesRef = useRef<HTMLDivElement>(null);
  const queryRef = useRef<HTMLTextAreaElement>(null);
  const requestRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const container = messagesRef.current;
      if (container) container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [messages, loading]);

  useEffect(() => {
    // React StrictMode runs setup -> cleanup -> setup in development.
    // Reset the flag on every setup so valid responses are not discarded.
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      requestRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    const clear = () => {
      requestRef.current?.abort();
      setMessages([{ id: 1, role: 'assistant', text: 'Chào bạn! Mình có thể tìm sân và khung giờ còn trống trực tiếp từ hệ thống SportHub. Bạn muốn chơi môn gì, ở đâu và khi nào?' }]);
      setQuery(''); setLoading(false); setContextFieldId(undefined); setSearchContext({});
    };
    window.addEventListener('sporthub-auth-cleared', clear);
    return () => window.removeEventListener('sporthub-auth-cleared', clear);
  }, []);

  const ask = async (value = query) => {
    const text = value.trim();
    if (!text || loading) return;
    setMessages((current) => [...current.map(clearInteractiveContent), { id: Date.now(), role: 'user', text }]);
    const location = text.match(/(?:ở|tại|quanh)\s+(.+?)(?:\s+(?:có|còn|không)|[?.!,]|$)/i)?.[1]?.trim();
    const partnerRequest = /chủ sân|đối tác|hồ sơ/i.test(text);
    setLoadingText(partnerRequest ? 'Đang kiểm tra hồ sơ đối tác...' : location ? `Đang tìm sân ở ${location}...` : 'Đang tìm sân phù hợp...');
    setQuery(''); setLoading(true);
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    try {
      const response = await askSportHubAssistant(text, contextFieldId, searchContext, controller.signal);
      if (!mountedRef.current || controller.signal.aborted) return;
      if (response.classification === 'OUT_OF_SCOPE') {
        setSearchContext({}); setContextFieldId(undefined);
      } else {
        setSearchContext(response.understood);
        if (response.suggestions[0]) setContextFieldId(response.suggestions[0].field_id);
        else if (response.venue_results[0]) setContextFieldId(response.venue_results[0].field_id);
        else if (response.context_reset) setContextFieldId(undefined);
      }
      setMessages((current) => [
        ...current.map(clearInteractiveContent),
        { id: Date.now() + 1, role: 'assistant', text: response.reply, suggestions: response.suggestions, venueResults: response.venue_results, classification: response.classification, intent: response.intent, uiStatus: response.classification === 'OUT_OF_SCOPE' ? 'OUT_OF_SCOPE' : response.status === 'OK' ? 'SUCCESS' : response.status, quickActions: quickActionsForResponse(response) },
      ]);
    } catch (error) {
      if (!mountedRef.current || controller.signal.aborted || (error instanceof DOMException && error.name === 'AbortError')) return;
      const errorText = error instanceof AssistantTimeoutError
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
    setQuery(value);
    window.requestAnimationFrame(() => queryRef.current?.focus());
  };
  const submit = (event: FormEvent) => { event.preventDefault(); void ask(); };

  return <div className="min-h-[calc(100vh-4rem)] bg-[radial-gradient(circle_at_top_left,_#ecfdf5,_transparent_35%),#f8fafc] px-3 py-5 sm:px-6 sm:py-8">
    <div className="mx-auto grid max-w-6xl gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
      <aside className="hidden rounded-3xl bg-brand-900 p-6 text-white shadow-xl lg:flex lg:flex-col">
        <div className="grid h-12 w-12 place-items-center rounded-2xl bg-brand-500"><Sparkles size={23} /></div>
        <h1 className="mt-5 text-2xl font-extrabold">Trợ lý SportHub</h1>
        <p className="mt-2 text-sm leading-6 text-slate-400">Tìm sân nhanh hơn bằng ngôn ngữ tự nhiên.</p>
        <div className="mt-8 space-y-3 text-sm">
          <p className="flex gap-3"><CalendarDays className="text-brand-400" size={18} /> Tìm theo ngày và giờ</p>
          <p className="flex gap-3"><MapPin className="text-brand-400" size={18} /> Lọc khu vực phù hợp</p>
          <p className="flex gap-3"><WalletCards className="text-brand-400" size={18} /> So khớp ngân sách</p>
        </div>
        <div className="mt-auto rounded-2xl border border-white/10 bg-white/5 p-4 text-xs leading-5 text-slate-400"><ShieldCheck className="mb-2 text-brand-400" size={20} />AI chỉ tìm kiếm và đề xuất. Bạn luôn là người xác nhận đặt sân và thanh toán.</div>
      </aside>

      <section className="flex h-[calc(100dvh-7rem)] min-h-[480px] max-h-[780px] min-w-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card sm:h-[76vh] sm:min-h-[560px] sm:rounded-3xl">
        <header className="flex items-center gap-3 border-b border-slate-100 px-4 py-4 sm:px-6">
          <span className="relative grid h-11 w-11 place-items-center rounded-2xl bg-ai-500 text-white"><Bot size={23} /><i className="absolute bottom-0 right-0 h-3 w-3 rounded-full border-2 border-white bg-emerald-300" /></span>
          <div><h1 className="font-bold text-slate-950">AI Trợ lý SportHub</h1><p className="text-xs text-slate-500">Dữ liệu sân & lịch trống theo thời gian thực</p></div>
          <Badge variant="success" className="ml-auto hidden sm:inline-flex" dot>Đang hoạt động</Badge>
        </header>

        <div ref={messagesRef} className="min-h-0 flex-1 space-y-5 overflow-y-auto bg-slate-50/60 p-4 sm:p-6">
          {messages.map((message) => <div key={message.id} className={`flex items-start gap-2.5 ${message.role === 'user' ? 'justify-end' : ''}`}>
            {message.role === 'assistant' && <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-brand-600 text-white"><Bot size={16} /></span>}
            <div className={`min-w-0 max-w-[94%] sm:max-w-[88%] ${message.role === 'user' ? 'order-first' : ''}`}>
              <div className={`rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === 'user' ? 'rounded-tr-md bg-brand-800 text-white' : 'rounded-tl-md border border-slate-200 bg-white text-slate-700 shadow-sm'}`}>{message.text}</div>
              {message.retryText && <Button className="mt-2" size="sm" variant="outline" onClick={() => void ask(message.retryText)}>Thử lại</Button>}
              {message.role === 'assistant' && message.classification && message.classification !== 'IN_SCOPE' && <p className="mt-1.5 text-[11px] font-semibold text-slate-400">{message.classification === 'OUT_OF_SCOPE' ? 'Ngoài phạm vi SportHub AI' : 'Cần làm rõ yêu cầu SportHub'}</p>}
              {!!message.suggestions?.length && <div className="mt-3 grid gap-3 xl:grid-cols-2">{message.suggestions.map((item) => <SuggestionCard key={`${item.field_id}-${item.time_slot_id}`} item={item} />)}</div>}
              {!!message.venueResults?.length && <div className="mt-3 grid gap-3 xl:grid-cols-2">{message.venueResults.map((item) => <VenueResultCard key={item.field_id} item={item} />)}</div>}
              <QuickActions actions={message.quickActions} onPrefill={applyQuickAction} />
            </div>
            {message.role === 'user' && <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-slate-200 text-slate-600"><UserRound size={16} /></span>}
          </div>)}
          {loading && <div className="flex items-center gap-2.5"><span className="grid h-8 w-8 place-items-center rounded-xl bg-brand-600 text-white"><Bot size={16} /></span><div className="flex items-center gap-2 rounded-2xl rounded-tl-md border bg-white px-4 py-3 text-sm text-slate-500"><span>{loadingText}</span><span className="flex gap-1"><i className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400" /><i className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:120ms]" /><i className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:240ms]" /></span></div></div>}
        </div>

        <footer className="border-t border-slate-100 bg-white p-3 sm:p-5">
          {messages.length === 1 && <div className="mb-3 flex gap-2 overflow-x-auto pb-1">{quickPrompts.map((prompt) => <button key={prompt} onClick={() => void ask(prompt)} className="shrink-0 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 hover:border-brand-300 hover:text-brand-700">{prompt}</button>)}</div>}
          <form onSubmit={submit} className="flex items-end gap-2 overflow-hidden rounded-2xl border border-slate-200 bg-slate-50 p-2 focus-within:border-brand-400 focus-within:ring-2 focus-within:ring-brand-100">
            <label htmlFor="assistant-query" className="sr-only">Nhập yêu cầu tìm sân</label>
            <textarea ref={queryRef} id="assistant-query" rows={1} value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void ask(); } }} placeholder="Ví dụ: Tối nay còn sân cầu lông nào?" className="max-h-28 min-h-10 flex-1 resize-none rounded-xl bg-transparent px-2 py-2 text-sm outline-none focus:outline-none focus-visible:outline-none" />
            <Button type="submit" disabled={!query.trim() || loading} aria-label="Gửi yêu cầu" className="h-10 w-10 shrink-0 p-0"><Send size={17} /></Button>
          </form>
          <p className="mt-2 text-center text-[11px] text-slate-400">Chỉ hỗ trợ nghiệp vụ SportHub AI. Dữ liệu cá nhân được giới hạn theo tài khoản và quyền đang đăng nhập.</p>
        </footer>
      </section>
    </div>
  </div>;
}

function QuickActions({ actions, onPrefill }: { actions?: QuickAction[]; onPrefill: (value: string) => void }) {
  if (!actions?.length) return null;
  return <div className="mt-2.5 flex flex-wrap gap-2">{actions.map((action) => action.kind === 'link'
    ? <Link key={action.label} to={action.value} className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-brand-300 hover:text-brand-700">{action.label}</Link>
    : <button key={action.label} type="button" onClick={() => onPrefill(action.value)} className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-brand-300 hover:text-brand-700">{action.label}</button>)}</div>;
}

function VenueResultCard({ item }: { item: AssistantVenueResult }) {
  return <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
    <p className="text-xs font-bold uppercase tracking-wide text-brand-700">{item.sport_type} · {item.court_type}</p>
    <h2 className="mt-1 font-bold text-slate-950">{item.facility_name}</h2>
    <p className="text-xs font-medium text-slate-500">Sân: {item.court_name}</p>
    <p className="mt-2 flex items-start gap-1.5 text-xs text-slate-500"><MapPin size={14} className="shrink-0" />{item.location}</p>
    <div className="mt-3 flex items-center justify-between"><b className="text-sm text-brand-700">Giá cơ bản từ {money(item.base_price)}</b><span className="text-xs text-amber-700"><Star size={12} className="mr-1 inline fill-current" />{item.rating.toFixed(1)}</span></div>
    <Link className="mt-4 block" to={`/courts/${item.field_id}`}><Button variant="outline" className="w-full">Xem sân và chọn lịch</Button></Link>
  </article>;
}

function SuggestionCard({ item }: { item: AssistantSuggestion }) {
  const slotIds = item.time_slot_ids?.length ? item.time_slot_ids : [item.time_slot_id];
  const slotQuery = slotIds.join(',');
  const rememberSelection = () => sessionStorage.setItem('sporthub_booking_context', JSON.stringify({
    venueId: item.facility_id, courtId: item.field_id, date: item.booking_date,
    slotId: item.time_slot_id, slotIds, startTime: item.start_time, endTime: item.end_time, price: item.price,
  }));
  return <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
    <div className="p-4">
      <div className="flex items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wide text-brand-700">{item.sport_type}{item.court_type ? ` · ${item.court_type}` : ''}</p><h2 className="mt-1 font-bold text-slate-950">{item.facility_name}</h2><p className="mt-0.5 text-xs font-medium text-slate-500">Sân: {item.court_name}</p></div>{item.is_nearest_alternative && <Badge variant="warning">Phương án gần nhất</Badge>}</div>
      <p className="mt-2 flex items-start gap-1.5 text-xs leading-5 text-slate-500"><MapPin size={14} className="mt-0.5 shrink-0" />{item.location}</p>
      <div className="mt-3 flex flex-wrap gap-2"><span className="rounded-lg bg-brand-50 px-2.5 py-1.5 text-xs font-semibold text-brand-700"><Clock3 size={13} className="mr-1 inline" />{item.selected_slots?.length > 1 ? `${item.selected_slots.length} khung giờ` : `${item.start_time}–${item.end_time}`} · {dateLabel(item.booking_date)}{item.duration_minutes ? ` · ${item.duration_minutes} phút` : ''}</span><span className="rounded-lg bg-slate-100 px-2.5 py-1.5 text-xs font-bold text-slate-700">{money(item.price)}</span><span className="rounded-lg bg-amber-50 px-2.5 py-1.5 text-xs font-semibold text-amber-700"><Star size={12} className="mr-1 inline fill-current" />{item.rating.toFixed(1)}</span><Badge variant="success">Còn trống</Badge></div>
      {item.selected_slots?.length > 1 && <p className="mt-2 text-xs text-slate-600">{item.selected_slots.map((slot) => `${slot.start_time.slice(0, 5)}–${slot.end_time.slice(0, 5)}`).join(', ')}</p>}
      <p className="mt-3 text-xs leading-5 text-slate-500"><b>Lý do AI gợi ý:</b> {item.reason}</p>
      <div className="mt-4 grid grid-cols-2 gap-2"><Link to={`/courts/${item.field_id}?date=${item.booking_date}&slot=${item.time_slot_id}&slots=${slotQuery}`}><Button variant="outline" className="w-full">Xem sân</Button></Link><Link onClick={rememberSelection} to={`/booking/${item.field_id}?date=${item.booking_date}&slot=${item.time_slot_id}&slots=${slotQuery}`}><Button className="w-full">Tiếp tục đặt <ChevronRight size={15} /></Button></Link></div>
    </div>
  </article>;
}
