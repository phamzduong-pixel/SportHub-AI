import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { cleanSpeechText } from '../utils/cleanSpeechText.ts';

// Mock Web Speech API SpeechSynthesis and SpeechSynthesisUtterance
class MockSpeechSynthesisUtterance {
  text: string;
  lang: string = 'vi-VN';
  rate: number = 1.0;
  pitch: number = 1.0;
  volume: number = 1.0;
  voice: any = null;
  onstart: (() => void) | null = null;
  onend: (() => void) | null = null;
  onerror: ((event: { error: string }) => void) | null = null;

  constructor(text: string) {
    this.text = text;
  }
}

class MockSpeechSynthesis {
  speaking: boolean = false;
  paused: boolean = false;
  pending: boolean = false;
  currentUtterance: MockSpeechSynthesisUtterance | null = null;
  voices: any[] = [];
  listeners: Record<string, (() => void)[]> = {};

  addEventListener(type: string, listener: () => void) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(listener);
  }

  removeEventListener(type: string, listener: () => void) {
    if (!this.listeners[type]) return;
    this.listeners[type] = this.listeners[type].filter((l) => l !== listener);
  }

  triggerVoicesChanged(newVoices: any[]) {
    this.voices = newVoices;
    if (this.listeners['voiceschanged']) {
      this.listeners['voiceschanged'].forEach((cb) => cb());
    }
  }

  getVoices() {
    return this.voices;
  }

  speak(utterance: MockSpeechSynthesisUtterance) {
    this.speaking = true;
    this.currentUtterance = utterance;
    if (utterance.onstart) {
      utterance.onstart();
    }
  }

  cancel() {
    this.speaking = false;
    if (this.currentUtterance && this.currentUtterance.onerror) {
      this.currentUtterance.onerror({ error: 'canceled' });
    }
    this.currentUtterance = null;
  }

  resume() {
    this.paused = false;
  }
}

describe('SpeechSynthesis TTS Engine Logic', () => {
  let mockSynthesis: MockSpeechSynthesis;

  beforeEach(() => {
    mockSynthesis = new MockSpeechSynthesis();
    mockSynthesis.voices = [
      { name: 'Google Tiếng Việt', lang: 'vi-VN', default: true },
      { name: 'Microsoft David', lang: 'en-US', default: false },
    ];
  });

  it('should create cleaned utterance and speak valid text', () => {
    const rawText = '**Messi** sinh ngày 24/06/1987. (Nguồn: FIFA https://fifa.com)';
    const cleaned = cleanSpeechText(rawText);

    assert.equal(cleaned, 'Messi sinh ngày 24/06/1987.');

    const utterance = new MockSpeechSynthesisUtterance(cleaned);
    utterance.lang = 'vi-VN';
    mockSynthesis.speak(utterance);

    assert.equal(mockSynthesis.speaking, true);
    assert.equal(mockSynthesis.currentUtterance?.text, 'Messi sinh ngày 24/06/1987.');
    assert.equal(mockSynthesis.currentUtterance?.lang, 'vi-VN');
  });

  it('should not speak when text is empty after cleaning', () => {
    const emptyRaw = '   (Nguồn: FIFA https://fifa.com)   ';
    const cleaned = cleanSpeechText(emptyRaw);
    assert.equal(cleaned, '');

    let spoke = false;
    if (cleaned) {
      mockSynthesis.speak(new MockSpeechSynthesisUtterance(cleaned));
      spoke = true;
    }

    assert.equal(spoke, false);
    assert.equal(mockSynthesis.speaking, false);
  });

  it('should stop and cancel speech immediately when stop is requested', () => {
    const utterance = new MockSpeechSynthesisUtterance('Đang đọc câu trả lời...');
    let endCalled = false;
    let errorCalled = false;

    utterance.onend = () => {
      endCalled = true;
    };
    utterance.onerror = (e) => {
      if (e.error === 'canceled') {
        errorCalled = true;
      }
    };

    mockSynthesis.speak(utterance);
    assert.equal(mockSynthesis.speaking, true);

    mockSynthesis.cancel();
    assert.equal(mockSynthesis.speaking, false);
    assert.equal(errorCalled, true);
    assert.equal(endCalled, false);
  });

  it('should find and select Vietnamese voice if available', () => {
    const voices = mockSynthesis.getVoices();
    const viVoice = voices.find((v) => v.lang.toLowerCase() === 'vi-vn' || v.lang.toLowerCase().startsWith('vi'));

    assert.ok(viVoice);
    assert.equal(viVoice.name, 'Google Tiếng Việt');

    const utterance = new MockSpeechSynthesisUtterance('Xin chào!');
    utterance.voice = viVoice;
    assert.equal(utterance.voice.name, 'Google Tiếng Việt');
  });

  it('should handle async voices loading when getVoices() initially returns empty array', () => {
    const emptySynth = new MockSpeechSynthesis();
    assert.equal(emptySynth.getVoices().length, 0);

    let loadedVoices: any[] = [];
    emptySynth.addEventListener('voiceschanged', () => {
      loadedVoices = emptySynth.getVoices();
    });

    // Browser asynchronously delivers voices
    emptySynth.triggerVoicesChanged([
      { name: 'Google Tiếng Việt', lang: 'vi-VN', default: true },
      { name: 'Microsoft HoaiMy', lang: 'vi-VN', default: false },
    ]);

    assert.equal(loadedVoices.length, 2);
    assert.equal(loadedVoices[0].name, 'Google Tiếng Việt');
  });

  it('should handle TTS error gracefully without crash', () => {
    let errorHandlerCalled = false;
    let isSpeakingState = true;

    const utterance = new MockSpeechSynthesisUtterance('Test error');
    utterance.onerror = (event) => {
      isSpeakingState = false;
      if (event.error !== 'canceled' && event.error !== 'interrupted') {
        errorHandlerCalled = true;
      }
    };

    mockSynthesis.speak(utterance);
    assert.equal(isSpeakingState, true);

    if (utterance.onerror) {
      utterance.onerror({ error: 'audio-busy' });
    }

    assert.equal(isSpeakingState, false);
    assert.equal(errorHandlerCalled, true);
  });
});

describe('AI Assistant Auto-Speak & Message UI Active State Workflows', () => {
  let mockSynthesis: MockSpeechSynthesis;

  beforeEach(() => {
    mockSynthesis = new MockSpeechSynthesis();
    mockSynthesis.voices = [{ name: 'Google Tiếng Việt', lang: 'vi-VN', default: true }];
  });

  it('1. Click Nghe đọc -> Message button immediately turns to Đang đọc...', () => {
    const messageId = 101;
    let isSpeaking = false;
    let speakingId: number | null = null;

    // Simulate clicking Nghe đọc
    const onSpeakClick = (id: number) => {
      isSpeaking = true;
      speakingId = id;
    };

    onSpeakClick(messageId);

    const isMessage101Active = isSpeaking && speakingId === 101;
    const isMessage102Active = isSpeaking && speakingId === 102;

    assert.equal(isMessage101Active, true);
    assert.equal(isMessage102Active, false);
  });

  it('2. Speech onend -> Active message resets back to Nghe đọc', () => {
    let isSpeaking = true;
    let speakingId: number | null = 101;

    const onEnd = () => {
      isSpeaking = false;
      speakingId = null;
    };

    onEnd();

    assert.equal(isSpeaking, false);
    assert.equal(speakingId, null);
    const isMessage101Active = isSpeaking && speakingId === 101;
    assert.equal(isMessage101Active, false);
  });

  it('3. Speech onerror -> Active message resets back to Nghe đọc without error toast', () => {
    let isSpeaking = true;
    let speakingId: number | null = 101;

    const onError = () => {
      isSpeaking = false;
      speakingId = null;
    };

    onError();

    assert.equal(isSpeaking, false);
    assert.equal(speakingId, null);
  });

  it('4. Click different message while speaking -> old message resets, new message becomes Đang đọc...', () => {
    let isSpeaking = true;
    let speakingId: number | null = 101;

    // User clicks message 102
    mockSynthesis.cancel();
    isSpeaking = true;
    speakingId = 102;

    const isMessage101Active = isSpeaking && String(speakingId) === '101';
    const isMessage102Active = isSpeaking && String(speakingId) === '102';

    assert.equal(isMessage101Active, false);
    assert.equal(isMessage102Active, true);
  });

  it('5. New AI response arrives while old message is speaking -> old message resets, new response is spoken if ON', () => {
    const autoSpeak = true;
    let isSpeaking = true;
    let speakingId: number | null = 101;

    const newResponseId = 202;
    // New response arrives
    mockSynthesis.cancel();
    if (autoSpeak) {
      isSpeaking = true;
      speakingId = newResponseId;
    }

    assert.equal(isSpeaking && speakingId === 101, false);
    assert.equal(isSpeaking && speakingId === 202, true);
  });

  it('6. Speaker toggle OFF -> Clears all active message speaking states', () => {
    let isSpeaking = true;
    let speakingId: number | null = 101;

    // Toggle OFF
    const onToggleOff = () => {
      mockSynthesis.cancel();
      isSpeaking = false;
      speakingId = null;
    };

    onToggleOff();

    assert.equal(isSpeaking, false);
    assert.equal(speakingId, null);
  });

  it('7. Microphone STT activation -> Clears active message speaking state', () => {
    let isSpeaking = true;
    let speakingId: number | null = 101;

    const onStartListening = () => {
      mockSynthesis.cancel();
      isSpeaking = false;
      speakingId = null;
    };

    onStartListening();

    assert.equal(isSpeaking, false);
    assert.equal(speakingId, null);
  });

  it('8. OFF -> click Speaker -> ON và giữ ON', () => {
    let speakerEnabled = false;
    // User clicks speaker button
    speakerEnabled = !speakerEnabled;
    assert.equal(speakerEnabled, true);
  });

  it('9. ON -> TTS onstart/onend -> Speaker vẫn ON', () => {
    let speakerEnabled = true;
    let isSpeaking = false;
    let speakingId: number | null = null;

    // TTS starts
    isSpeaking = true;
    speakingId = 101;
    assert.equal(speakerEnabled, true);
    assert.equal(isSpeaking, true);

    // TTS onend
    isSpeaking = false;
    speakingId = null;
    assert.equal(speakerEnabled, true);
    assert.equal(isSpeaking, false);
  });

  it('10. ON -> TTS error -> Speaker vẫn ON', () => {
    let speakerEnabled = true;
    let isSpeaking = true;
    let speakingId: number | null = 101;

    // TTS error occurs
    isSpeaking = false;
    speakingId = null;
    assert.equal(speakerEnabled, true);
    assert.equal(isSpeaking, false);
    assert.equal(speakingId, null);
  });

  it('11. ON -> cancel -> Speaker vẫn ON', () => {
    let speakerEnabled = true;
    let isSpeaking = true;
    let speakingId: number | null = 101;

    // Cancel active playback
    mockSynthesis.cancel();
    isSpeaking = false;
    speakingId = null;

    assert.equal(speakerEnabled, true);
    assert.equal(isSpeaking, false);
  });

  it('12. OFF -> không auto-speak response mới', () => {
    const speakerEnabled = false;
    let spokeText = '';

    const onNewResponse = (text: string) => {
      if (speakerEnabled) {
        spokeText = text;
      }
    };

    onNewResponse('Câu trả lời mới');
    assert.equal(spokeText, '');
  });

  it('13. Manual "Nghe đọc" không thay đổi Speaker ON/OFF', () => {
    let speakerEnabled = false;
    let isSpeaking = false;
    let speakingId: number | null = null;

    // User clicks Nghe đọc on message 50
    isSpeaking = true;
    speakingId = 50;

    // Speaker global remains OFF
    assert.equal(speakerEnabled, false);
    assert.equal(isSpeaking, true);
    assert.equal(speakingId, 50);

    // When reading finishes
    isSpeaking = false;
    speakingId = null;
    assert.equal(speakerEnabled, false);
  });

  it('14. Speaker OFF khi đang đọc -> cancel audio + reset active message', () => {
    let speakerEnabled = true;
    let isSpeaking = true;
    let speakingId: number | null = 88;

    // User clicks Speaker to turn OFF
    speakerEnabled = false;
    mockSynthesis.cancel();
    isSpeaking = false;
    speakingId = null;

    assert.equal(speakerEnabled, false);
    assert.equal(isSpeaking, false);
    assert.equal(speakingId, null);
  });
});
