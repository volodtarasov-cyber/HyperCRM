/* ============================================================
   ЛЕВША · ПЛЁНКА · MVP-ЛЕНДИНГ · interactions
   ============================================================ */

(function () {
  'use strict';

  /* ---------- Бургер-меню ---------- */
  const burger = document.getElementById('burger');
  const nav = document.querySelector('.header__nav');
  if (burger && nav) {
    burger.addEventListener('click', () => {
      nav.classList.toggle('header__nav--open');
    });
    // Закрывать меню при клике на пункт
    nav.querySelectorAll('a').forEach(a =>
      a.addEventListener('click', () => nav.classList.remove('header__nav--open'))
    );
  }

  /* ---------- Квиз ---------- */
  const quiz = document.getElementById('quiz');
  if (quiz) {
    const steps = quiz.querySelectorAll('.quiz__step:not(.quiz__done)');
    const doneStep = quiz.querySelector('.quiz__done');
    const stepCounter = document.getElementById('quizStep');
    const progressBar = document.getElementById('quizBar');
    const total = steps.length;
    let current = 0;
    const answers = {};

    function showStep(idx, autoFocus = true) {
      steps.forEach((s, i) => s.classList.toggle('quiz__step--active', i === idx));
      if (doneStep) doneStep.classList.remove('quiz__step--active');
      stepCounter.textContent = idx + 1;
      progressBar.style.width = ((idx + 1) / total) * 100 + '%';
      if (!autoFocus) return;
      const firstInput = steps[idx].querySelector('input[type=text], input[type=tel]');
      // preventScroll: чтобы при ручном переключении шагов страница не прыгала к квизу
      if (firstInput) setTimeout(() => firstInput.focus({ preventScroll: true }), 100);
    }

    function showDone() {
      steps.forEach(s => s.classList.remove('quiz__step--active'));
      doneStep.classList.add('quiz__step--active');
      progressBar.style.width = '100%';
      stepCounter.textContent = total;
    }

    function nextStep() {
      const step = steps[current];
      // сохранить значение текущего шага
      const text = step.querySelector('input[type=text], input[type=tel]');
      if (text) answers[text.dataset.field || 'field_' + current] = text.value.trim();
      const radio = step.querySelector('input[type=radio]:checked');
      if (radio) answers[radio.name] = radio.value;

      current++;
      if (current >= total) {
        submit();
      } else {
        showStep(current);
      }
    }

    function submit() {
      // Здесь будет интеграция с Б24 / Telegram-бот / форма-приёмник.
      // Пока — выводим в консоль и показываем экран «спасибо».
      console.log('Quiz submitted:', answers);
      showDone();
    }

    // Радио-кнопки переходят на след. шаг сами
    quiz.addEventListener('change', e => {
      if (e.target.matches('input[type=radio]')) {
        setTimeout(nextStep, 250);
      }
    });

    // Текстовые шаги — по кнопке «Дальше →»
    quiz.querySelectorAll('.quiz__next').forEach(btn =>
      btn.addEventListener('click', e => {
        e.preventDefault();
        const step = steps[current];
        const input = step.querySelector('input[type=text], input[type=tel]');
        if (input && !input.value.trim()) {
          input.focus();
          input.style.borderColor = '#e34a4a';
          return;
        }
        nextStep();
      })
    );

    // Финальная кнопка «Получить расчёт»
    const submitBtn = quiz.querySelector('.quiz__submit');
    if (submitBtn) {
      submitBtn.addEventListener('click', e => {
        e.preventDefault();
        const step = steps[current];
        const inputs = step.querySelectorAll('input[type=text], input[type=tel]');
        let valid = true;
        inputs.forEach(i => {
          if (!i.value.trim()) {
            i.style.borderColor = '#e34a4a';
            valid = false;
          }
        });
        if (!valid) return;
        nextStep();
      });
    }

    // На первой загрузке — без автофокуса, чтобы страница не прыгала к квизу
    showStep(0, false);
  }

  /* ---------- Финальная форма ---------- */
  const finalForm = document.getElementById('finalForm');
  if (finalForm) {
    finalForm.addEventListener('submit', e => {
      e.preventDefault();
      const data = {
        name: finalForm.querySelector('input[type=text]').value.trim(),
        phone: finalForm.querySelector('input[type=tel]').value.trim()
      };
      console.log('Final form submitted:', data);
      finalForm.innerHTML =
        '<p style="margin:0;padding:20px;background:rgba(255,255,255,.15);' +
        'border-radius:8px;font-size:17px;">✅ Спасибо! Перезвоним в течение рабочего дня.</p>';
    });
  }

  /* ============================================================
     STORIES
     ============================================================ */
  const STORY_DATA = {
    reviews: {
      title: 'Отзывы клиентов',
      slides: [
        {
          icon: '🎥',
          title: 'Видео-отзыв',
          desc: 'Клиент рассказывает, как изменилась машина после шумоизоляции: «трассу почти не слышно». Вертикальное видео 9:16, 20–30 сек.'
        },
        {
          icon: '⭐',
          title: 'Скрин Я.Карт',
          desc: 'Скриншот 5-звёздочного отзыва с Яндекс.Карт про шумоизоляцию: тишина в салоне, аккуратная сборка. Видны дата и имя клиента.'
        },
        {
          icon: '📸',
          title: 'Фото + цитата',
          desc: 'Фото клиента у машины + крупная цитата: «Думал, в новой машине так и должно гудеть. Оказалось — нет». Имя и марка под фото.'
        },
        {
          icon: '🎥',
          title: 'Видео-отзыв №2',
          desc: 'Меломан про акустику: «Двери перестали дышать, басы встали на место». 30 сек, вертикаль.'
        }
      ]
    },
    cases: {
      title: 'Кейсы работ',
      slides: [
        {
          icon: '🚗',
          title: 'Haval Jolion · комплекс',
          desc: 'Слайд-сравнение зон до/после шумоизоляции. Подпись: STP Aero, комплекс без арок, 3 дня. Боль сегмента «новая машина гудит» — снята.'
        },
        {
          icon: '⏱',
          title: 'Тайм-лапс работы',
          desc: 'Ускоренное видео 20–30 сек: разбор двери → укладка виброизоляции и шумопоглотителя → сборка. Финал — глухой «премиум» звук двери.'
        },
        {
          icon: '📋',
          title: 'Chery Tiggo · цифры',
          desc: 'Фото машины + инфографика: что шумоизолировали (двери/пол/арки), материал STP Aero, сколько слоёв, сколько дней, пакет.'
        },
        {
          icon: '🔍',
          title: 'Двери · слои',
          desc: 'Макро готовой двери: ровные слои материала, всё собрано без зазоров. Подпись: «Что сняли — поставили назад. Без скрипов».'
        }
      ]
    },
    about: {
      title: 'Знакомство с Левшой',
      slides: [
        {
          icon: '🏢',
          title: 'Цех изнутри',
          desc: 'Фото цеха Левши: рабочий свет, машина в разборе, чистый пол. Подпись: «Детейлинг-центр с 2015 года, не гараж».'
        },
        {
          icon: '👤',
          title: 'Мастер цеха',
          desc: 'Портрет профильного мастера шумоизоляции, фон — цех. Подпись: «6 лет руками. Читает машину и находит источник шума».'
        },
        {
          icon: '🎥',
          title: 'Тур по студии',
          desc: 'Видео 30 сек от входа до цеха: ресепшен → зона ожидания → цех шумоизоляции. Снимать с плеча, живо.'
        },
        {
          icon: '🏆',
          title: 'Награды',
          desc: 'Скрин «751 оценка 5,0» на Яндекс.Картах. Текст: «№1 в Самаре по числу оценок среди детейлинг-центров».'
        }
      ]
    },
    process: {
      title: 'Как мы делаем тишину',
      slides: [
        {
          icon: '🔇',
          title: '01 · Диагностика',
          desc: 'Видео: мастер слушает машину и определяет источник шума. Подпись: «Найдём, откуда звучит, и не дадим переплатить за лишнее».'
        },
        {
          icon: '📸',
          title: '02 · Разбор и фиксация',
          desc: 'Тайм-лапс: аккуратный разбор салона, фото каждого этапа. Подпись: «Всё зафиксировано — что сняли, то и поставим назад».'
        },
        {
          icon: '🧱',
          title: '03 · Шумоизоляция слоями',
          desc: 'Макро: укладка виброизоляции и шумопоглотителя STP Aero. Подпись: «Под задачу, а не ради объёма».'
        },
        {
          icon: '✅',
          title: '04 · Сборка без скрипов',
          desc: 'Сборка салона под точку, проверка на скрипы. Подпись: «Главная боль рынка — закрыта на сборке, не на словах».'
        }
      ]
    }
  };

  const viewer = document.getElementById('storyViewer');
  if (viewer) {
    const slideEl = document.getElementById('storySlide');
    const progressEl = document.getElementById('storyProgress');
    const titleEl = document.getElementById('storyTitle');
    const closeBtn = document.getElementById('storyClose');
    const prevBtn = document.getElementById('storyPrev');
    const nextBtn = document.getElementById('storyNext');
    const triggers = document.querySelectorAll('.story');

    let currentKey = null;
    let currentIdx = 0;
    let autoTimer = null;

    function openStory(key) {
      currentKey = key;
      currentIdx = 0;
      viewer.classList.add('story-viewer--open');
      viewer.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
      render();
      // отметить «просмотрено»
      const trig = document.querySelector('.story[data-story="' + key + '"]');
      if (trig) trig.classList.add('story--seen');
    }

    function closeStory() {
      viewer.classList.remove('story-viewer--open');
      viewer.setAttribute('aria-hidden', 'true');
      document.body.style.overflow = '';
      clearTimeout(autoTimer);
      currentKey = null;
    }

    function render() {
      const data = STORY_DATA[currentKey];
      if (!data) return;
      const slide = data.slides[currentIdx];
      if (!slide) return;

      titleEl.textContent = data.title;

      // прогресс-бары
      progressEl.innerHTML = '';
      data.slides.forEach((_, i) => {
        const seg = document.createElement('span');
        if (i < currentIdx) seg.classList.add('is-done');
        if (i === currentIdx) seg.classList.add('is-active');
        progressEl.appendChild(seg);
      });

      // содержимое слайда (плейсхолдер под фото/видео)
      slideEl.innerHTML =
        '<div class="story-viewer__placeholder">' +
          '<div class="story-viewer__placeholder-icon">' + slide.icon + '</div>' +
          '<p><strong>' + slide.title + '</strong>' + slide.desc + '</p>' +
        '</div>';

      // автопереход через 5 сек
      clearTimeout(autoTimer);
      autoTimer = setTimeout(nextSlide, 5000);
    }

    function nextSlide() {
      const data = STORY_DATA[currentKey];
      if (!data) return;
      if (currentIdx < data.slides.length - 1) {
        currentIdx++;
        render();
      } else {
        // конец коллекции — перейти к следующей
        const keys = Object.keys(STORY_DATA);
        const currentI = keys.indexOf(currentKey);
        const nextKey = keys[currentI + 1];
        if (nextKey) {
          openStory(nextKey);
        } else {
          closeStory();
        }
      }
    }

    function prevSlide() {
      if (currentIdx > 0) {
        currentIdx--;
        render();
      } else {
        // в начало предыдущей коллекции
        const keys = Object.keys(STORY_DATA);
        const currentI = keys.indexOf(currentKey);
        const prevKey = keys[currentI - 1];
        if (prevKey) {
          currentKey = prevKey;
          currentIdx = STORY_DATA[prevKey].slides.length - 1;
          render();
        }
      }
    }

    triggers.forEach(t =>
      t.addEventListener('click', () => openStory(t.dataset.story))
    );
    closeBtn.addEventListener('click', closeStory);
    nextBtn.addEventListener('click', nextSlide);
    prevBtn.addEventListener('click', prevSlide);

    // клавиатура
    document.addEventListener('keydown', e => {
      if (!viewer.classList.contains('story-viewer--open')) return;
      if (e.key === 'Escape') closeStory();
      if (e.key === 'ArrowRight') nextSlide();
      if (e.key === 'ArrowLeft') prevSlide();
    });

    // клик по фону — закрыть
    viewer.addEventListener('click', e => {
      if (e.target === viewer) closeStory();
    });
  }

  /* ============================================================
     VIDEO MODAL (этапы работы)
     ============================================================ */
  const PROCESS_VIDEOS = {
    'step-1': {
      title: 'Диагностика источника шума',
      caption: 'Зачем это нужно: за 15–20 минут находим, откуда у вашей машины идёт основной гул — арки, двери, пол или дребезг пластика. Часто хватает точечно, и мы честно скажем, если комплекс не нужен. Бесплатно, без обязательств.',
      placeholder: {
        icon: '🎥',
        title: 'Видео 30–40 сек',
        desc: 'Мастер слушает машину, при возможности — на ходу. Показывает на зоны-источники шума, объясняет клиенту, с чего начать.'
      }
    },
    'step-2': {
      title: 'Разбор салона и фиксация',
      caption: 'Аккуратно разбираем нужные зоны и фиксируем каждый этап. Что сняли — клипсы, фиксаторы, разъёмы — всё помечено и встанет на место. Главный страх рынка (после разбора «поедет по швам») закрыт уже на этом этапе.',
      placeholder: {
        icon: '🎥',
        title: 'Видео 40–60 сек',
        desc: 'Тайм-лапс разбора двери/пола. Крупно — снятые клипсы разложены по местам. Голосом за кадром: «Всё вернём, как было, только тише».'
      }
    },
    'step-3': {
      title: 'Шумоизоляция слоями',
      caption: 'Укладываем виброизоляцию и шумопоглотитель STP Aero — официальную заводскую линейку, не безымянное «что было на складе». Слои — под задачу зоны, а не «обмотать всё ради чека». Зимой материал работает ещё и как утеплитель.',
      placeholder: {
        icon: '🎥',
        title: 'Видео 60 сек',
        desc: 'Макро: раскатка виброизоляции по металлу, прикатка валиком, сверху — шумопоглотитель. Видна ровная аккуратная укладка.'
      }
    },
    'step-4': {
      title: 'Сборка без скрипов',
      caption: 'Собираем салон под точку: каждая клипса и разъём — на место. Проверяем на скрипы и зазоры до выдачи. Если что-то «играет» — устраняем сразу. Главное отличие от гаража: машина не начинает звучать как старая.',
      placeholder: {
        icon: '🎥',
        title: 'Видео 30 сек',
        desc: 'Сборка двери, защёлкивание клипс, закрытие — глухой плотный звук. Мастер проводит рукой по пластику, проверяет на люфт.'
      }
    },
    'step-5': {
      title: 'Выдача, проверка тишины, гарантия',
      caption: 'Сдаём машину с договором и гарантией 1 год: заскрипит или отойдёт — бесплатно поправим. Через 7 дней звоним узнать, как тишина. Через 30 дней приглашаем на бесплатный контрольный осмотр.',
      placeholder: {
        icon: '🎥',
        title: 'Видео 30 сек',
        desc: 'Клиент закрывает дверь, слушает разницу. Крупно — договор и гарантийный талон в руках. Финал: машина в цеху, краткая благодарность.'
      }
    }
  };

  const videoModal = document.getElementById('videoModal');
  if (videoModal) {
    const mediaEl = document.getElementById('videoMedia');
    const titleEl = document.getElementById('videoTitle');
    const descEl = document.getElementById('videoDesc');
    const closeBtn = document.getElementById('videoClose');

    function openVideo(key) {
      const data = PROCESS_VIDEOS[key];
      if (!data) return;

      titleEl.textContent = data.title;
      descEl.textContent = data.caption;
      mediaEl.innerHTML =
        '<div class="video-modal__placeholder">' +
          '<div class="video-modal__placeholder-icon">' + data.placeholder.icon + '</div>' +
          '<p><strong>' + data.placeholder.title + '</strong>' + data.placeholder.desc + '</p>' +
        '</div>';

      videoModal.classList.add('video-modal--open');
      videoModal.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
    }

    function closeVideo() {
      videoModal.classList.remove('video-modal--open');
      videoModal.setAttribute('aria-hidden', 'true');
      document.body.style.overflow = '';
      mediaEl.innerHTML = '';
    }

    document.querySelectorAll('.process__photo').forEach(btn =>
      btn.addEventListener('click', () => openVideo(btn.dataset.video))
    );
    closeBtn.addEventListener('click', closeVideo);

    document.addEventListener('keydown', e => {
      if (videoModal.classList.contains('video-modal--open') && e.key === 'Escape') {
        closeVideo();
      }
    });

    videoModal.addEventListener('click', e => {
      if (e.target === videoModal) closeVideo();
    });
  }

  /* ============================================================
     360° VIEWER (горизонтальный обзор машины)
     ============================================================ */
  const spinViewer = document.getElementById('spin360viewer');
  if (spinViewer) {
    const total = parseInt(spinViewer.dataset.frames, 10) || 36;
    const path = spinViewer.dataset.path || 'assets/spin360/';
    const fmt = spinViewer.dataset.format || 'jpg';
    const canvas = document.getElementById('spin360canvas');
    const placeholder = spinViewer.querySelector('.spin360__placeholder');

    function frameSrc(i) {
      const n = String(i + 1).padStart(2, '0');
      return path + n + '.' + fmt;
    }

    // Пробуем загрузить первый кадр — если его нет, оставляем плейсхолдер.
    const probe = new Image();
    probe.onload = () => initSpin();
    probe.onerror = () => {
      // фото не залиты — плейсхолдер остаётся, ничего не делаем
    };
    probe.src = frameSrc(0);

    function initSpin() {
      const frames = [];
      let loaded = 0;
      let currentIdx = 0;
      let autoTimer = null;
      const ctx = canvas.getContext('2d');

      for (let i = 0; i < total; i++) {
        const img = new Image();
        img.onload = () => {
          loaded++;
          if (loaded === total) onReady();
        };
        img.src = frameSrc(i);
        frames.push(img);
      }

      function onReady() {
        placeholder.style.display = 'none';
        canvas.hidden = false;
        const w = frames[0].naturalWidth;
        const h = frames[0].naturalHeight;
        canvas.width = w;
        canvas.height = h;
        draw();
        startAuto();
        bindDrag();
      }

      function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(frames[currentIdx], 0, 0);
      }

      function startAuto() {
        stopAuto();
        autoTimer = setInterval(() => {
          currentIdx = (currentIdx + 1) % total;
          draw();
        }, 80);
      }
      function stopAuto() { if (autoTimer) clearInterval(autoTimer); autoTimer = null; }

      function bindDrag() {
        let startX = 0, startIdx = 0, dragging = false;
        const sensitivity = 12; // пикселей на 1 кадр

        spinViewer.addEventListener('pointerdown', e => {
          dragging = true;
          startX = e.clientX;
          startIdx = currentIdx;
          stopAuto();
          spinViewer.setPointerCapture(e.pointerId);
        });
        spinViewer.addEventListener('pointermove', e => {
          if (!dragging) return;
          const delta = e.clientX - startX;
          const shift = Math.round(delta / sensitivity);
          currentIdx = ((startIdx - shift) % total + total) % total;
          draw();
        });
        const end = e => {
          dragging = false;
          try { spinViewer.releasePointerCapture(e.pointerId); } catch {}
          // через 3 сек после взаимодействия — снова авто-крутка
          setTimeout(() => { if (!dragging) startAuto(); }, 3000);
        };
        spinViewer.addEventListener('pointerup', end);
        spinViewer.addEventListener('pointercancel', end);
      }
    }
  }

  /* ---------- Smooth scroll для якорей ---------- */
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', e => {
      const href = a.getAttribute('href');
      if (href === '#' || href.length < 2) return;
      const target = document.querySelector(href);
      if (target) {
        e.preventDefault();
        const offset = 80;
        const top = target.getBoundingClientRect().top + window.pageYOffset - offset;
        window.scrollTo({ top, behavior: 'smooth' });
      }
    });
  });

})();
