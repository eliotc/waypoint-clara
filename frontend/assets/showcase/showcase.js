/* Fixed-script live example. No microphone or recorded-response fallback. */
(() => {
  'use strict';
  const el = id => document.getElementById(id);
  // On phones the progress panel stacks above the stage, so bring the active
  // column into view when it starts. Desktop layouts are left untouched.
  const revealOnNarrow = node => {
    if (!node || typeof node.scrollIntoView !== 'function' || typeof window.matchMedia !== 'function') return;
    if (window.matchMedia('(max-width: 800px)').matches) node.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };
  let socket = null, audio = null, running = false, generation = 0;
  let runId = null, turnId = null, lastSeq = 0, nextTime = 0;
  let sources = new Set(), completed = false, heard = false, acknowledged = false;
  let bubbles = new Map(), scenario = null;
  let hoodOn = true;
  let evalProgressInterval = null;
  const traceEls = {};

  function esc(s) {
    return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function highlightJson(obj) {
    const json = JSON.stringify(obj, null, 2);
    return esc(json).replace(
      /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)/g,
      m => {
        let cls = 'n';
        if (/^"/.test(m)) cls = /:$/.test(m) ? 'k' : 's';
        else if (/true|false|null/.test(m)) cls = 'b';
        return `<span class="${cls}">${m}</span>`;
      }
    );
  }

  function setHood(on) {
    hoodOn = on;
    const container = document.querySelector('.showcase-container');
    if (container && container.classList) container.classList.toggle('hood-on', on);
    const btn = el('hoodToggle');
    if (btn && btn.classList) {
      btn.classList.toggle('on', on);
      btn.setAttribute('aria-pressed', String(on));
    }
  }

  function renderToolCall(msg) {
    const callKey = msg.id || `${msg.turn_id}-${msg.name}`;
    if (traceEls[callKey]) return;
    const card = el(`turn-${msg.turn_id}`);
    if (!card) return;

    const trace = document.createElement('div');
    trace.className = 'via-trace collapsed';
    trace.dataset.start = String((typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now());

    const head = document.createElement('div');
    head.className = 'via-trace-head';
    head.innerHTML = `
      <span class="via-trace-bolt"><span class="material-symbols-rounded">database</span></span>
      <span class="via-trace-name">${esc(msg.name)}</span>
      <span class="via-trace-toggle-hint">
        <span class="hint-collapsed"><span class="material-symbols-rounded">expand_more</span> View query &amp; response</span>
        <span class="hint-expanded"><span class="material-symbols-rounded">expand_less</span> Hide details</span>
      </span>
      <span class="via-trace-status">
        <span class="via-trace-spinner"></span>
        <span class="via-trace-caret"><span class="material-symbols-rounded">keyboard_arrow_down</span></span>
      </span>
    `;
    head.addEventListener('click', () => {
      if (trace.classList && trace.classList.toggle) {
        trace.classList.toggle('collapsed');
      } else {
        trace.className = trace.className.indexOf('collapsed') !== -1 ? 'via-trace' : 'via-trace collapsed';
      }
    });

    const body = document.createElement('div');
    body.className = 'via-trace-body';
    const inputDiv = document.createElement('div');
    inputDiv.innerHTML = `
      <div class="via-trace-io-label">Input query</div>
      <pre class="via-trace-pre">${highlightJson(msg.args || {})}</pre>
    `;
    body.append(inputDiv);
    trace.append(head, body);

    const claraRow = card.querySelector?.('.clara-row');
    if (claraRow && card.insertBefore) {
      card.insertBefore(trace, claraRow);
    } else {
      card.append(trace);
    }
    traceEls[callKey] = trace;
  }

  function renderToolResult(msg) {
    const callKey = msg.id || `${msg.turn_id}-${msg.name}`;
    const trace = traceEls[callKey];
    if (!trace) return;

    const start = parseFloat(trace.dataset.start || '0');
    const now = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
    const secs = start ? ((now - start) / 1000).toFixed(2) : null;

    const status = trace.querySelector?.('.via-trace-status');
    if (status) {
      const spinner = status.querySelector?.('.via-trace-spinner');
      if (spinner && spinner.remove) spinner.remove();

      let statusHtml = '';
      if (secs) statusHtml += `<span class="via-trace-latency">${secs}s</span>`;
      statusHtml += `<span class="via-trace-check"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg></span>`;
      if (status.insertAdjacentHTML) {
        status.insertAdjacentHTML('afterbegin', statusHtml);
      } else {
        status.innerHTML = statusHtml;
      }
    }

    const body = trace.querySelector?.('.via-trace-body');
    if (body) {
      const out = document.createElement('div');
      out.innerHTML = `
        <div class="via-trace-io-label out">Result summary</div>
        <pre class="via-trace-pre">${highlightJson(msg.response || msg.result || {})}</pre>
      `;
      body.append(out);
    }
  }

  function setProgress(percent) {
    const bar = el('showcaseProgressBar');
    if (bar && bar.style) bar.style.width = `${Math.min(100, Math.max(0, percent))}%`;
  }

  let userHasScrolledUp = false;

  function getScrollTargetTop(element, container) {
    if (!element || !container) return 0;
    if (typeof element.getBoundingClientRect === 'function' && typeof container.getBoundingClientRect === 'function') {
      const elemRect = element.getBoundingClientRect();
      const contRect = container.getBoundingClientRect();
      return elemRect.top - contRect.top + (container.scrollTop || 0);
    }
    let top = 0;
    let current = element;
    while (current && current !== container) {
      if (typeof current.offsetTop === 'number') {
        top += current.offsetTop;
      }
      current = current.offsetParent;
    }
    return top;
  }

  function scrollStreamToTurn(card) {
    const stream = el('conversationStream');
    if (!stream || !card) return;
    userHasScrolledUp = false;
    updateJumpButton(false);

    const targetTop = getScrollTargetTop(card, stream);
    if (stream.scrollTo) {
      stream.scrollTo({
        top: Math.max(0, targetTop),
        behavior: 'smooth'
      });
    } else {
      stream.scrollTop = Math.max(0, targetTop);
    }
  }

  function updateJumpButton(show) {
    const jumpBtn = el('btnScrollToCurrent');
    if (jumpBtn && jumpBtn.style) {
      jumpBtn.style.display = show ? 'flex' : 'none';
    }
  }

  function setupScrollTracking() {
    const stream = el('conversationStream');
    const jumpBtn = el('btnScrollToCurrent');
    if (!stream || !stream.addEventListener) return;

    stream.addEventListener('scroll', () => {
      const activeCard = stream.querySelector?.('.turn-card.active-turn');
      if (!activeCard) {
        updateJumpButton(false);
        return;
      }
      const activeTop = getScrollTargetTop(activeCard, stream);
      const isScrolledAway = Math.abs(stream.scrollTop - activeTop) > 60;
      userHasScrolledUp = Boolean(isScrolledAway);
      updateJumpButton(userHasScrolledUp);
    }, { passive: true });

    if (jumpBtn && jumpBtn.addEventListener) {
      jumpBtn.addEventListener('click', () => {
        const activeCard = stream.querySelector?.('.turn-card.active-turn');
        if (activeCard) {
          scrollStreamToTurn(activeCard);
        }
      });
    }
  }

  function renderQuestionPills() {
    const bar = el('questionPillsBar');
    if (!bar || !scenario) return;
    bar.replaceChildren();
    const count = scenario.student_messages.length;
    for (let i = 0; i < count; i++) {
      const pill = document.createElement('div');
      pill.className = 'q-pill';
      pill.id = `q-pill-${i + 1}`;
      pill.title = `Click to view Question ${i + 1}`;
      pill.style.cursor = 'pointer';

      const num = document.createElement('span');
      num.className = 'q-pill-num';
      num.textContent = `${i + 1}`;
      const title = document.createElement('span');
      title.className = 'q-pill-title';
      title.textContent = scenario.turn_labels?.[i] || `Q${i + 1}`;
      pill.append(num, title);

      pill.addEventListener('click', () => {
        const targetCard = el(`turn-${i + 1}`);
        const stream = el('conversationStream');
        if (targetCard && stream) {
          const top = getScrollTargetTop(targetCard, stream);
          if (stream.scrollTo) {
            stream.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
          } else {
            stream.scrollTop = Math.max(0, top);
          }
        }
      });

      bar.append(pill);
    }
  }

  function updateQuestionPills(currentTurn) {
    if (!scenario) return;
    const count = scenario.student_messages.length;
    for (let i = 1; i <= count; i++) {
      const pill = el(`q-pill-${i}`);
      if (!pill) continue;
      const num = pill.querySelector('.q-pill-num');
      const liveDot = pill.querySelector('.q-pill-live-dot');
      if (i < currentTurn) {
        pill.className = 'q-pill completed';
        if (num) num.textContent = '✓';
        if (liveDot && liveDot.remove) liveDot.remove();
      } else if (i === currentTurn) {
        pill.className = 'q-pill active';
        if (num) num.textContent = `${i}`;
        const title = pill.querySelector('.q-pill-title');
        if (title && !liveDot) {
          const dot = document.createElement('span');
          dot.className = 'q-pill-live-dot';
          dot.textContent = '●';
          title.append(dot);
        }
      } else {
        pill.className = 'q-pill';
        if (num) num.textContent = `${i}`;
        if (liveDot && liveDot.remove) liveDot.remove();
      }
    }
  }

  function turnAudioDone(id) {
    const card = el(`turn-${id}`);
    if (card) card.className = 'turn-card active-turn';
    const bubble = el(`clara-bubble-${id}`);
    if (bubble) bubble.className = 'speech-bubble bubble-clara';
    const badge = el(`clara-badge-${id}`);
    if (badge) {
      badge.className = 'speaking-done-badge';
      badge.textContent = '✓ Answer complete';
    }
    const statusBadge = el(`turn-badge-status-${id}`);
    if (statusBadge) {
      statusBadge.className = 'turn-status-badge done';
      statusBadge.textContent = '✓ Completed';
    }
    const pill = el(`q-pill-${id}`);
    if (pill) {
      pill.className = 'q-pill completed';
      const num = pill.querySelector('.q-pill-num');
      if (num) num.textContent = '✓';
    }
    if (scenario) {
      const total = scenario.student_messages.length;
      setProgress(10 + (id / total) * 75);
    }
  }

  function triggerStepTransitionFlash() {
    const col1 = el('stepCol-1');
    const col2 = el('stepCol-2');
    const badge1 = el('stepBadge-1');
    const badge2 = el('stepBadge-2');
    const connector = el('stepConnectorLine');
    const recCols = el('recordingColumns');
    const sub2 = col2 ? col2.querySelector('.step-caption') : null;

    if (col1) {
      col1.classList.remove('completed-flash');
      void col1.offsetWidth;
      col1.classList.add('completed-flash');
      col1.classList.add('completed');
      if (badge1) badge1.textContent = '✓';
    }

    if (connector) {
      connector.classList.add('active', 'streaming');
      setTimeout(() => connector.classList.remove('streaming'), 1500);
    }

    if (col2) {
      col2.classList.remove('step2-attention-flash');
      void col2.offsetWidth;
      col2.classList.add('active', 'step2-attention-flash');
      if (badge2) {
        badge2.innerHTML = '<span class="material-symbols-rounded spin-slow" style="font-size:14px;">autorenew</span>';
      }
      if (sub2) {
        sub2.innerHTML = '<span class="step-live-pulse-dot"></span><span>Auditing 6 turns against catalog…</span>';
      }
    }

    if (recCols) {
      recCols.classList.remove('stage-transition-flash');
      void recCols.offsetWidth;
      recCols.classList.add('stage-transition-flash');
      setTimeout(() => recCols.classList.remove('stage-transition-flash'), 1200);
    }
  }

  function setStepFocus(step) {
    const idleCard = el('stageIdleState');
    const recCols = el('recordingColumns');
    const convCol = el('conversationColumn');
    const splitter = el('panelSplitter');
    const findCol = el('findingsColumn');
    const step1Pill = el('step1TagPill');
    const step2Pill = el('step2TagPill');
    const step1Note = el('step1StreamNote');
    const step2Note = el('step2StreamNote');
    const evalBanner = el('evaluatingBanner');
    const evalStatus = el('step2EvalStatus');
    const intro = el('resultsIntro');

    if (step === 1) {
      if (idleCard) idleCard.style.display = 'none';
      if (recCols) recCols.style.display = 'flex';
      if (convCol && convCol.classList) {
        convCol.classList.add('is-active-step', 'is-single-column');
        convCol.classList.remove('is-completed-step');
      }
      if (splitter) splitter.style.display = 'none';
      if (findCol && findCol.classList) {
        findCol.style.display = 'none';
        findCol.classList.remove('is-active-step', 'is-evaluating');
        findCol.classList.add('is-waiting-step');
      }
      if (step1Pill) {
        step1Pill.className = 'step-tag-pill active';
        step1Pill.textContent = running ? 'Step 1 · In Progress' : 'Step 1';
      }
      if (step2Pill) {
        step2Pill.className = 'step-tag-pill muted';
        step2Pill.textContent = 'Step 2 · Up Next';
      }
      if (step2Note) step2Note.textContent = 'Automated AI audit (runs after dialogue)';
      if (evalBanner) evalBanner.style.display = 'none';
      if (evalStatus) evalStatus.style.display = 'none';
      if (intro) intro.style.display = '';
    } else if (step === 2) {
      if (idleCard) idleCard.style.display = 'none';
      if (recCols) recCols.style.display = 'flex';
      if (convCol && convCol.classList) {
        convCol.classList.remove('is-active-step', 'is-single-column');
        convCol.classList.add('is-completed-step');
      }
      if (splitter) splitter.style.display = 'flex';
      if (findCol && findCol.classList) {
        findCol.style.display = 'flex';
        findCol.classList.remove('is-waiting-step');
        findCol.classList.add('is-active-step', 'is-evaluating', 'anim-enter');
      }
      if (step1Pill) {
        step1Pill.className = 'step-tag-pill done';
        step1Pill.textContent = 'Step 1 · Complete';
      }
      if (step1Note) step1Note.textContent = 'All 6 turns completed';
      if (step2Pill) {
        step2Pill.className = 'step-tag-pill active pulse';
        step2Pill.textContent = 'Step 2 · Checking Facts Now…';
      }
      if (step2Note) step2Note.textContent = 'AI evaluation in progress (~15–20s)';
      if (evalBanner) evalBanner.style.display = 'flex';
      if (evalStatus) evalStatus.style.display = 'flex';
      if (intro) intro.style.display = 'none';
      triggerStepTransitionFlash();
    } else if (step === 'complete') {
      if (idleCard) idleCard.style.display = 'none';
      if (recCols) recCols.style.display = 'flex';
      if (convCol && convCol.classList) {
        convCol.classList.remove('is-active-step', 'is-single-column');
        convCol.classList.add('is-completed-step');
      }
      if (splitter) splitter.style.display = 'flex';
      if (findCol && findCol.classList) {
        findCol.style.display = 'flex';
        findCol.classList.remove('is-evaluating', 'is-waiting-step');
        findCol.classList.add('is-active-step');
      }
      if (step1Pill) {
        step1Pill.className = 'step-tag-pill done';
        step1Pill.textContent = 'Step 1 · Complete';
      }
      if (step2Pill) {
        step2Pill.className = 'step-tag-pill done';
        step2Pill.textContent = 'Step 2 · Complete';
      }
      if (step2Note) step2Note.textContent = 'AI evaluation complete';
      if (evalBanner) evalBanner.style.display = 'none';
      if (evalStatus) evalStatus.style.display = 'none';
      if (intro) intro.style.display = '';
    }
  }

  function updateStepIndicator(stepNumber) {
    for (let i = 1; i <= 2; i++) {
      const col = el(`stepCol-${i}`);
      const badge = el(`stepBadge-${i}`);
      if (!col) continue;
      if (i === stepNumber) {
        col.className = 'sidebar-step-card active';
        if (badge) badge.textContent = `${i}`;
      } else if (i < stepNumber) {
        col.className = 'sidebar-step-card completed';
        if (badge) badge.textContent = '✓';
      } else {
        col.className = 'sidebar-step-card';
        if (badge) badge.textContent = `${i}`;
      }
    }
    const connector = el('stepConnectorLine');
    if (connector) {
      connector.classList.toggle('active', stepNumber === 2);
    }
    const dot = el('globalStatusDot');
    if (dot && dot.classList && dot.classList.toggle) {
      dot.classList.toggle('pulse', stepNumber === 1 || stepNumber === 2);
    }
  }

  function stage(index, detail) {
    for (let i=0;i<4;i++) {
      const node=el(`stage-${i}`);
      if(node) {
        if(i===index) node.setAttribute('aria-current','step'); else node.removeAttribute('aria-current');
        node.setAttribute('data-complete',String(i<index));
      }
    }
    const detailEl = el('progressDetail');
    if (detailEl) detailEl.textContent=detail;

    if (index === 0 || index === 1) {
      updateStepIndicator(1);
      setStepFocus(1);
    } else if (index === 2) {
      updateStepIndicator(2);
      setStepFocus(2);
    } else if (index === 3) {
      updateStepIndicator(2);
      const b2 = el('stepBadge-2');
      if (b2) b2.textContent = '✓';
      const col2 = el('stepCol-2');
      if (col2) col2.className = 'sidebar-step-card completed';
      setStepFocus('complete');
    }
  }

  function status(text) {
    const p = el('statusPill'); if (p) p.textContent = text;
    const l = el('liveStatusText'); if (l) l.textContent = text;
  }

  function cleanup() {
    generation++;
    const old = socket; socket = null;
    if (old) { old.onclose = null; old.onmessage = null; old.onerror = null; old.onopen = null; old.close(); }
    for (const source of sources) { source.onended = null; try { source.stop(); } catch (_) {} }
    sources.clear();
    if (audio) { audio.onstatechange = null; audio.close().catch(() => {}); audio = null; }
    running = false;
  }

  function end(message) {
    cleanup(); status(message);
    const bar = el('liveControlsBar'); if (bar) bar.style.display = 'none';
    const actions = el('postRunActions'); if (actions) actions.style.display = 'block';
    const btnStart = el('btnStartLive');
    if (btnStart) {
      btnStart.disabled = false;
      btnStart.innerHTML = '<span>▶ Replay Walkthrough</span>';
    }
  }

  function fail(message) {
    end('Example stopped');
    const detail = el('progressDetail');
    if (detail) detail.textContent='This attempt did not finish. No completed evaluation is available.';
    const p = document.createElement('p'); p.setAttribute('role','alert'); p.textContent = message;
    const stream = el('conversationStream'); if (stream) stream.append(p);
    const btnStart = el('btnStartLive');
    if (btnStart) {
      btnStart.disabled = false;
      btnStart.innerHTML = '<span>▶ Start Walkthrough</span>';
    }
  }

  function ack() {
    if (!running || !completed || acknowledged || !heard || sources.size) return;
    if (!audio || audio.state !== 'running') { fail('Audio playback is unavailable. The example has stopped.'); return; }
    acknowledged = true;
    turnAudioDone(turnId);
    socket.send(JSON.stringify({action:'playback_ack',run_id:runId,turn_id:turnId}));
  }

  function play(data) {
    if (!audio || audio.state !== 'running') throw new Error('Audio playback is unavailable.');
    const bytes = Uint8Array.from(atob(data), c=>c.charCodeAt(0));
    if (!bytes.length || bytes.length % 2) throw new Error('Invalid audio response.');
    const view = new DataView(bytes.buffer), buffer = audio.createBuffer(1,bytes.length/2,24000);
    const channel = buffer.getChannelData(0);
    for (let i=0;i<channel.length;i++) channel[i]=view.getInt16(i*2,true)/32768;
    const source=audio.createBufferSource(); source.buffer=buffer; source.connect(audio.destination);
    sources.add(source); heard=true;
    source.onended=()=>{sources.delete(source);ack();};
    nextTime=Math.max(nextTime,audio.currentTime+0.02); source.start(nextTime); nextTime+=buffer.duration;
  }

  function turn(message) {
    if (sources.size) throw new Error('Previous audio has not finished.');
    turnId=message.turn_id; completed=false; heard=false; acknowledged=false;
    const total = scenario.student_messages.length;
    const turnLabel = scenario.turn_labels?.[turnId-1] || 'Exploring options';

    const stream = el('conversationStream');
    if (stream && stream.querySelectorAll) {
      const prevActive = stream.querySelectorAll('.turn-card.active-turn');
      prevActive.forEach(c => {
        c.className = 'turn-card completed-turn';
        const sBadge = c.querySelector?.('.turn-status-badge');
        if (sBadge) {
          sBadge.className = 'turn-status-badge done';
          sBadge.innerHTML = '<span class="material-symbols-rounded">check</span><span>Completed</span>';
        }
      });
    }

    const card=document.createElement('article');
    card.className='turn-card active-turn';
    card.id=`turn-${turnId}`;

    // Header: Question number, live focus tag & topic
    const header=document.createElement('div');
    header.className='turn-card-header';

    const leftHeader=document.createElement('div');
    leftHeader.style.display='flex';
    leftHeader.style.alignItems='center';
    leftHeader.style.gap='8px';

    const turnPill=document.createElement('span');
    turnPill.className='turn-badge';
    turnPill.textContent=`Question ${turnId} of ${total}`;

    const step1Pill = el('step1TagPill');
    if (step1Pill) {
      step1Pill.className = 'step-tag-pill active';
      step1Pill.textContent = `Step 1 · Question ${turnId} of ${total}`;
    }
    const step1Note = el('step1StreamNote');
    if (step1Note) {
      step1Note.textContent = `Question ${turnId} of ${total} streaming live`;
    }

    const liveBadgeTag=document.createElement('span');
    liveBadgeTag.className='turn-status-badge live';
    liveBadgeTag.id=`turn-badge-status-${turnId}`;
    liveBadgeTag.innerHTML='<span class="turn-status-pulse"></span><span>Current turn</span>';

    leftHeader.append(turnPill, liveBadgeTag);

    const topicBadge = document.createElement('div');
    topicBadge.className = 'turn-topic-badge';
    topicBadge.id = `turn-topic-${turnId}`;
    topicBadge.innerHTML = `
      <span class="topic-tag-prefix">Focus topic</span>
      <span class="topic-tag-title">${esc(turnLabel)}</span>
    `;
    header.append(leftHeader, topicBadge);

    // Row 1: Alex's question
    const studentRow=document.createElement('div');
    studentRow.className='speech-bubble-row student-row';
    const studentAvatar=document.createElement('div');
    studentAvatar.className='avatar-placeholder-alex-sm';
    studentAvatar.textContent='A';
    studentAvatar.title='Alex (Student Persona)';

    const studentContent=document.createElement('div');
    studentContent.className='student-content-wrap';

    const studentHeader=document.createElement('div');
    studentHeader.className='student-speech-header';
    studentHeader.innerHTML=`
      <span class="student-name-tag">Alex (Student)</span>
      <span class="student-speaking-hint"><span class="material-symbols-rounded">chat_bubble</span><span>Question prompt</span></span>
    `;

    const studentBubble=document.createElement('div');
    studentBubble.className='speech-bubble bubble-student';
    studentBubble.textContent=message.text;

    studentContent.append(studentHeader, studentBubble);
    studentRow.append(studentAvatar, studentContent);

    // Row 2: Clara's live answer
    const claraRow=document.createElement('div');
    claraRow.className='speech-bubble-row clara-row';
    const claraAvatar=document.createElement('div');
    claraAvatar.className='avatar-placeholder-clara-sm';
    claraAvatar.textContent='C';
    claraAvatar.title='Clara (AI Counsellor)';

    const claraContent=document.createElement('div');
    claraContent.style.flex='1';
    claraContent.style.display='flex';
    claraContent.style.flexDirection='column';

    const claraBubble=document.createElement('div');
    claraBubble.className='speech-bubble bubble-clara is-speaking';
    claraBubble.id=`clara-bubble-${turnId}`;
    claraBubble.textContent='Waiting for Clara’s response…';

    const liveBadge=document.createElement('span');
    liveBadge.className='speaking-live-badge';
    liveBadge.id=`clara-badge-${turnId}`;
    const w1=document.createElement('span'); w1.className='wave-bar';
    const w2=document.createElement('span'); w2.className='wave-bar';
    const w3=document.createElement('span'); w3.className='wave-bar';
    const badgeText=document.createElement('span');
    badgeText.textContent=' Clara speaking live…';
    liveBadge.append(w1, w2, w3, badgeText);

    claraContent.append(claraBubble, liveBadge);
    claraRow.append(claraAvatar, claraContent);

    card.append(header, studentRow, claraRow);
    if (stream) {
      stream.append(card);
      if (typeof requestAnimationFrame === 'function') {
        requestAnimationFrame(() => {
          scrollStreamToTurn(card);
        });
      } else {
        scrollStreamToTurn(card);
      }
    }
    bubbles.set(turnId, claraBubble);

    // Update progress bar & pills
    updateStepIndicator(2);
    updateQuestionPills(turnId);
    setProgress(10 + ((turnId - 0.5) / total) * 75);

    stage(1,'Listen to Clara’s response. The next question follows when the audio finishes.');
    status(`Question ${turnId} of ${total} · ${turnLabel}`);
  }

  function renderToolEvaluationCard(toolEval) {
    if (!toolEval) return null;
    const card = document.createElement('section');
    card.className = `tool-eval-card ${toolEval.passed ? 'compliant' : 'non-compliant'}`;
    card.id = 'toolEvaluationCard';

    const header = document.createElement('div');
    header.className = 'tool-eval-header';

    const titleGroup = document.createElement('div');
    titleGroup.className = 'tool-eval-title-group';

    const badge = document.createElement('span');
    badge.className = `tool-eval-badge ${toolEval.passed ? 'pass' : 'warning'}`;
    badge.innerHTML = toolEval.passed ? `<span class="material-symbols-rounded">check</span><span>${toolEval.turns_compliant}/${toolEval.total_turns} turns compliant</span>` : `<span class="material-symbols-rounded">warning</span><span>Protocol issue</span>`;

    const title = document.createElement('h3');
    title.textContent = 'Tool protocol & telemetry policy';
    titleGroup.append(badge, title);

    header.append(titleGroup);

    const summary = document.createElement('p');
    summary.className = 'finding-summary';
    summary.textContent = toolEval.summary || '';

    const drawer = document.createElement('details');
    drawer.className = 'tool-eval-turns-breakdown';
    drawer.open = false;

    const drawerSum = document.createElement('summary');
    drawerSum.innerHTML = `<span>See turn-by-turn verification breakdown (${toolEval.turns_compliant}/${toolEval.total_turns})</span> <span class="material-symbols-rounded drawer-caret">expand_more</span>`;
    drawer.append(drawerSum);

    const turnsList = document.createElement('div');
    turnsList.className = 'tool-eval-turns-list';

    for (const te of (toolEval.turn_evaluations || [])) {
      const row = document.createElement('div');
      row.className = 'tool-turn-row';

      const rowHead = document.createElement('div');
      rowHead.className = 'tool-turn-row-head';

      const leftLabel = document.createElement('span');
      leftLabel.className = 'tool-turn-label';
      leftLabel.textContent = `Question ${te.turn_id}: ${te.phase}`;

      const statusPill = document.createElement('span');
      statusPill.className = `tool-turn-status-pill ${te.passed ? 'pass' : 'fail'}`;
      statusPill.innerHTML = te.passed ? '<span class="material-symbols-rounded">check</span><span>Compliant</span>' : '<span class="material-symbols-rounded">warning</span><span>Flagged</span>';

      rowHead.append(leftLabel, statusPill);

      const note = document.createElement('div');
      note.className = 'tool-turn-note';
      note.textContent = te.outcome || te.notes || '';

      row.append(rowHead, note);

      if (te.technical_detail) {
        const tech = document.createElement('div');
        tech.className = 'tool-turn-tech-detail';
        tech.textContent = `Technical: ${te.technical_detail}`;
        row.append(tech);
      }

      turnsList.append(row);
    }
    drawer.append(turnsList);

    card.append(header, summary, drawer);
    return card;
  }

  function results(message) {
    const checksCard = el('technicalChecksCard');
    if (checksCard) checksCard.style.display='block';
    const checks=message.technical_checks;
    const toolEval = message.tool_evaluation || (checks && checks.tool_evaluation);
    const list = el('technicalChecksList');
    if (list) {
      list.replaceChildren();
      const checkItems = [
        checks.audio_received ? 'Audio received' : 'No audio received',
        checks.expected_turns_completed ? `All ${scenario.student_messages.length} questions completed` : 'Conversation incomplete',
        `Execution: ${checks.run_status}`,
        `Tools observed: ${checks.tool_invocations.join(', ') || 'None'}`
      ];
      if (toolEval && toolEval.summary) {
        checkItems.push(`Tool evaluation: ${toolEval.summary}`);
      }
      for (const text of checkItems) {
        const li = document.createElement('li');
        li.textContent = text;
        list.append(li);
      }
    }
    const evalBanner = el('evaluatingBanner'); if (evalBanner) evalBanner.style.display = 'none';
    const evalStatus = el('step2EvalStatus'); if (evalStatus) evalStatus.style.display = 'none';
    const intro = el('resultsIntro');
    if (intro) {
      intro.style.display = '';
      intro.textContent='These are provisional AI checks of this dialogue. Open the evidence to see why each finding was made.';
    }
    const recap=bubbles.get(scenario.student_messages.length);
    const outcomeRecap = el('outcomeRecap');
    if (outcomeRecap) {
      outcomeRecap.replaceChildren(); outcomeRecap.hidden=!recap;
      if(recap) {
        const heading=document.createElement('h3');heading.textContent='Clara’s closing advice';
        const body=document.createElement('p');body.textContent=recap.textContent;
        const note=document.createElement('p');note.textContent='This is Clara’s answer, not a verified recommendation. The checks below may identify limitations.';
        outcomeRecap.append(heading,body,note);
      }
    }
    const findingsStream = el('findingsStream');
    if (findingsStream) findingsStream.replaceChildren();

    // Render Deterministic Tool Evaluation Card
    if (toolEval) {
      const toolCard = renderToolEvaluationCard(toolEval);
      if (toolCard && findingsStream) findingsStream.append(toolCard);
    }

    const titles=Object.fromEntries(scenario.criteria.map(c=>[c.id,c.title]));
    for (const finding of message.quality_findings) {
      const card=document.createElement('section');
      const statusClass = 'finding-' + (finding.status || 'unknown').replaceAll('_', '-');
      card.className = `finding-card ${statusClass}`;
      const title=document.createElement('h3');title.textContent=titles[finding.criterion_id];
      const label=document.createElement('span');
      label.className = `finding-status-badge badge-${(finding.status || '').replaceAll('_', '-')}`;
      const statusIcon = finding.status === 'supported' ? 'check_circle' : (finding.status === 'issue_observed' ? 'warning' : 'help');
      const statusLabel = {
        supported: 'Supported by conversation',
        issue_observed: 'Attention required',
        unable_to_assess: 'Unable to assess'
      }[finding.status] || finding.status;
      label.innerHTML = `<span class="material-symbols-rounded finding-badge-icon">${statusIcon}</span><span>${statusLabel}</span>`;
      const summary=document.createElement('p');summary.className='finding-summary';summary.textContent=finding.summary;
      card.append(title,label,summary);
      for (const evidence of finding.evidence) {
        const details=document.createElement('details');details.className='finding-evidence-drawer';
        const heading=document.createElement('summary');
        heading.innerHTML = `<span>${evidence.kind==='tool'?'See course database record':'See what Clara said'}</span> <span class="material-symbols-rounded drawer-caret">expand_more</span>`;
        const quote=document.createElement('blockquote');quote.textContent=evidence.quote==='null' && evidence.kind==='tool' ? `${(evidence.field || 'This detail').replaceAll('_',' ')}: not recorded` : evidence.quote;
        const link=document.createElement('a');link.className='evidence-turn-link';link.href=`#turn-${evidence.turn_id}`;
        link.innerHTML = `<span>Jump to question ${evidence.turn_id}</span> <span class="material-symbols-rounded">arrow_forward</span>`;
        details.append(heading,quote,link);card.append(details);
      }
      if (findingsStream) findingsStream.append(card);
    }
  }

  async function start() {
    if (running || !scenario) return;
    cleanup(); running=true;
    const ownGeneration=generation;
    const preRun = el('preRunCard'); if (preRun) preRun.style.display='none';
    const postRun = el('postRunActions'); if (postRun) postRun.style.display='none';
    const liveBar = el('liveControlsBar'); if (liveBar) liveBar.style.display='flex';
    const convStream = el('conversationStream'); if (convStream) convStream.replaceChildren();
    const findStream = el('findingsStream'); if (findStream) findStream.replaceChildren();
    const checksCard = el('technicalChecksCard'); if (checksCard) checksCard.style.display='none';
    const pillsBar = el('questionPillsBar'); if (pillsBar) pillsBar.style.display='flex';

    runId=null;turnId=null;lastSeq=0;nextTime=0;bubbles=new Map();
    for (const k in traceEls) delete traceEls[k];
    const outcomeRecap = el('outcomeRecap'); if (outcomeRecap) outcomeRecap.hidden=true;
    const evalBanner = el('evaluatingBanner'); if (evalBanner) evalBanner.style.display='none';
    const evalStatus = el('step2EvalStatus'); if (evalStatus) evalStatus.style.display='none';
    const intro = el('resultsIntro'); if (intro) { intro.style.display=''; intro.textContent='Checks will appear after the dialogue completes.'; }

    setProgress(5);
    updateQuestionPills(0);
    setStepFocus(1);
    stage(1,'Starting a fresh dialogue for Alex. No microphone is needed.');
    status('Connecting to Clara…');
    revealOnNarrow(el('conversationColumn'));

    try {
      const Audio=window.AudioContext||window.webkitAudioContext;
      if (!Audio) throw new Error('This browser cannot play the live audio.');
      audio=new Audio({sampleRate:24000});await audio.resume();
      if (ownGeneration!==generation) return;
      if (audio.state!=='running') throw new Error('Enable audio playback before starting the example.');
      audio.onstatechange=()=>{if(running && audio && audio.state!=='running') fail('Audio playback was interrupted. Please restart the example.');};
      const current=new WebSocket(`${location.protocol==='https:'?'wss:':'ws:'}//${location.host}/ws/showcase/live`);socket=current;
      current.onopen=()=>{if(socket===current) current.send(JSON.stringify({action:'start',scenario_id:scenario.id}));};
      current.onmessage=event=>{
        if(socket!==current || !running) return;
        try {
          const message=JSON.parse(event.data);
          if(message.type==='error') {fail(message.message);return;}
          if(!runId) runId=message.run_id;
          if(message.run_id!==runId || !Number.isInteger(message.seq) || message.seq<=lastSeq) return;
          lastSeq=message.seq;
          if(message.type==='turn_start') { turn(message); if (message.turn_id===1) revealOnNarrow(el('conversationColumn')); }
          else if(message.type==='audio' && message.turn_id===turnId) play(message.data);
          else if(message.type==='transcript' && message.turn_id===turnId) {
            const b = bubbles.get(turnId); if (b) b.textContent=message.text;
          }
          else if(message.type==='tool_call') renderToolCall(message);
          else if(message.type==='tool_result') renderToolResult(message);
          else if(message.type==='agent_turn_complete' && message.turn_id===turnId) {completed=true;if(!heard) throw new Error('No playable audio was received.');ack();}
          else if(message.type==='results') results(message);
          else if(message.type==='status') {
            if(message.state==='checking') {
              setProgress(92);
              updateQuestionPills(scenario.student_messages.length + 1);
              stage(2,'Running Quality & Fact Check against course catalog evidence (~15–20s)…');
              status('Running Quality & Fact Check…');
              revealOnNarrow(el('findingsColumn'));
            }
            if(message.state==='completed') {
              setProgress(100);
              stage(3,'Quality & Fact Check complete. Review findings below.');
              end('Quality & Fact Check complete');
            }
          }
        } catch(error) {fail(error.message || 'The live response could not be read.');}
      };
      current.onerror=()=>{if(socket===current) fail('The live connection failed.');};
      current.onclose=()=>{if(socket===current && running) fail('The connection closed before the example finished.');};
    } catch(error) {if(ownGeneration===generation) fail(error.message);}
  }

  const btnStart = el('btnStartLive');
  if (btnStart) {
    btnStart.disabled=true;
    btnStart.addEventListener('click',start);
  }
  const btnStop = el('btnStopLive');
  if (btnStop) {
    btnStop.addEventListener('click',()=>{
      if(socket?.readyState===WebSocket.OPEN) socket.send(JSON.stringify({action:'stop'}));
      end('Stopped by you');
      const detail = el('progressDetail');
      if (detail) detail.textContent='The dialogue has stopped. Start again for a fresh walkthrough.';
      setStepFocus(1);
    });
  }
  const btnAgain = el('btnRunAgain');
  if (btnAgain) {
    btnAgain.addEventListener('click',()=>{
      cleanup();
      const preRun = el('preRunCard'); if (preRun) preRun.style.display='block';
      const postRun = el('postRunActions'); if (postRun) postRun.style.display='none';
      const convStream = el('conversationStream'); if (convStream) convStream.replaceChildren();
      const findStream = el('findingsStream'); if (findStream) findStream.replaceChildren();
      const checksCard = el('technicalChecksCard'); if (checksCard) checksCard.style.display='none';
      const outcomeRecap = el('outcomeRecap'); if (outcomeRecap) outcomeRecap.hidden=true;
      const pillsBar = el('questionPillsBar'); if (pillsBar) pillsBar.style.display='none';
      const evalBanner = el('evaluatingBanner'); if (evalBanner) evalBanner.style.display='none';
      const evalStatus = el('step2EvalStatus'); if (evalStatus) evalStatus.style.display='none';
      for (const k in traceEls) delete traceEls[k];
      setProgress(0);
      updateStepIndicator(1);
      setStepFocus(1);
      stage(0,'A fixed student story. Fresh answers from Clara.');
      status('Meet Alex before you start.');
    });
  }

  const btnHood = el('hoodToggle');
  if (btnHood) {
    btnHood.addEventListener('click', () => setHood(!hoodOn));
  }

  const storage = typeof localStorage !== 'undefined' ? localStorage : { getItem: () => null, setItem: () => {}, removeItem: () => {} };

  function setupSidebarCollapse() {
    const sidebar = el('showcaseSidebar');
    const toggleBtn = el('btnToggleSidebar');
    if (!sidebar || !toggleBtn) return;

    const savedState = storage.getItem('waypoint_sidebar_collapsed');
    if (savedState === 'true') {
      sidebar.classList.add('collapsed');
      toggleBtn.title = 'Expand progress panel';
      toggleBtn.setAttribute('aria-label', 'Expand progress panel');
    }

    toggleBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isCollapsed = sidebar.classList.toggle('collapsed');
      storage.setItem('waypoint_sidebar_collapsed', isCollapsed ? 'true' : 'false');
      toggleBtn.title = isCollapsed ? 'Expand progress panel' : 'Collapse progress panel';
      toggleBtn.setAttribute('aria-label', toggleBtn.title);
    });
  }

  function setupPanelResize() {
    const splitter = el('panelSplitter');
    const container = el('recordingColumns');
    const conversationCol = el('conversationColumn');
    const findingsCol = el('findingsColumn');
    if (!splitter || !container || !conversationCol || !findingsCol) return;

    const savedWidth = storage.getItem('waypoint_findings_width');
    if (savedWidth) {
      const parsed = parseInt(savedWidth, 10);
      if (parsed >= 280 && parsed <= 800) {
        findingsCol.style.width = `${parsed}px`;
      }
    }

    let isDragging = false;
    let startX = 0;
    let startWidth = 0;

    function onPointerDown(e) {
      isDragging = true;
      startX = e.clientX || (e.touches && e.touches[0].clientX) || 0;
      startWidth = typeof findingsCol.getBoundingClientRect === 'function' ? findingsCol.getBoundingClientRect().width : 420;
      splitter.classList.add('is-dragging');
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';

      window.addEventListener('mousemove', onPointerMove);
      window.addEventListener('mouseup', onPointerUp);
      window.addEventListener('touchmove', onPointerMove, { passive: false });
      window.addEventListener('touchend', onPointerUp);
    }

    function onPointerMove(e) {
      if (!isDragging) return;
      if (e.cancelable) e.preventDefault();
      const clientX = e.clientX || (e.touches && e.touches[0].clientX) || 0;
      const deltaX = clientX - startX;
      const containerWidth = typeof container.getBoundingClientRect === 'function' ? container.getBoundingClientRect().width : 1000;
      let newWidth = startWidth - deltaX;

      const maxFindingsWidth = Math.max(280, containerWidth - 320);
      newWidth = Math.max(280, Math.min(newWidth, Math.min(800, maxFindingsWidth)));

      findingsCol.style.width = `${newWidth}px`;
    }

    function onPointerUp() {
      if (!isDragging) return;
      isDragging = false;
      splitter.classList.remove('is-dragging');
      document.body.style.cursor = '';
      document.body.style.userSelect = '';

      window.removeEventListener('mousemove', onPointerMove);
      window.removeEventListener('mouseup', onPointerUp);
      window.removeEventListener('touchmove', onPointerMove);
      window.removeEventListener('touchend', onPointerUp);

      const finalWidth = typeof findingsCol.getBoundingClientRect === 'function' ? findingsCol.getBoundingClientRect().width : newWidth;
      storage.setItem('waypoint_findings_width', Math.round(finalWidth).toString());
    }

    splitter.addEventListener('mousedown', onPointerDown);
    splitter.addEventListener('touchstart', onPointerDown, { passive: true });

    splitter.addEventListener('dblclick', () => {
      findingsCol.style.width = '420px';
      storage.removeItem('waypoint_findings_width');
    });
  }

  setupSidebarCollapse();
  setupPanelResize();
  setupScrollTracking();

  window.addEventListener('pagehide',cleanup);
  fetch('/api/showcase/scenario/returning-to-study').then(r=>{if(!r.ok)throw new Error();return r.json();}).then(data=>{
    scenario=data;
    const title = el('example-title'); if (title) title.textContent=data.title;
    const sub = el('exampleSubtitle'); if (sub) sub.textContent=data.subtitle;
    const preRun = el('preRunCard');
    if (preRun) {
      const list=preRun.querySelector('ol');
      if (list) {
        list.replaceChildren();
        for(const text of data.student_messages){const li=document.createElement('li');li.textContent=text;list.append(li);}
      }
    }
    const visitorCriteria = el('visitorCriteria');
    if (visitorCriteria) {
      visitorCriteria.replaceChildren();
      for(const criterion of data.criteria){
        const li=document.createElement('li'),title=document.createElement('strong'),body=document.createElement('span');
        title.textContent=criterion.title;body.textContent=criterion.description;li.append(title,body);visitorCriteria.append(li);
      }
    }
    renderQuestionPills();
    if (btnStart) btnStart.disabled=false;
  }).catch(()=>{status('Example unavailable');});
})();