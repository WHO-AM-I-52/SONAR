/**
 * filter_chips.js — Feature #5 FilterBar
 * Быстрые chip-фильтры над таблицей обращений.
 * Фильтрует строки <tbody> без перезагрузки страницы.
 */

(function () {
  'use strict';

  // ── Активное состояние фильтров ──────────────────────────────────────────
  const state = {
    status: null,     // string | null
    employee: null,   // string | null  (нормализованное имя)
    date: null        // 'today' | 'week' | 'month' | null
  };

  // ── Вспомогательные функции ──────────────────────────────────────────────
  function today() {
    return new Date().toISOString().slice(0, 10);
  }

  function weeksAgo(n) {
    const d = new Date();
    d.setDate(d.getDate() - n * 7);
    return d.toISOString().slice(0, 10);
  }

  function monthsAgo(n) {
    const d = new Date();
    d.setMonth(d.getMonth() - n);
    return d.toISOString().slice(0, 10);
  }

  // ── Основная функция фильтрации ──────────────────────────────────────────
  function applyFilters() {
    const rows = document.querySelectorAll('#requests-tbody tr[data-status]');
    let visible = 0;

    rows.forEach(function (row) {
      let show = true;

      // Фильтр по статусу
      if (state.status) {
        show = show && (row.dataset.status === state.status);
      }

      // Фильтр по ответственному
      if (state.employee) {
        const emp = (row.dataset.employee || '').toLowerCase().trim();
        show = show && (emp === state.employee.toLowerCase().trim());
      }

      // Фильтр по дате
      if (state.date) {
        const rowDate = (row.dataset.date || '').slice(0, 10);
        if (rowDate) {
          const t = today();
          if (state.date === 'today') {
            show = show && (rowDate === t);
          } else if (state.date === 'week') {
            show = show && (rowDate >= weeksAgo(1) && rowDate <= t);
          } else if (state.date === 'month') {
            show = show && (rowDate >= monthsAgo(1) && rowDate <= t);
          }
        } else {
          show = false;
        }
      }

      row.style.display = show ? '' : 'none';
      if (show) visible++;
    });

    // Обновляем счётчик
    const counter = document.getElementById('chip-visible-count');
    if (counter) {
      const total = rows.length;
      counter.textContent = visible === total
        ? 'Все записи: ' + total
        : 'Показано: ' + visible + ' из ' + total;
    }

    // Показываем/скрываем «пусто»
    let emptyRow = document.getElementById('chip-empty-row');
    if (visible === 0) {
      if (!emptyRow) {
        emptyRow = document.createElement('tr');
        emptyRow.id = 'chip-empty-row';
        emptyRow.innerHTML = '<td colspan="13" class="text-center text-muted py-4">' +
          '<i class="bi bi-funnel" style="font-size:1.5rem;display:block"></i>' +
          'Нет записей по выбранным фильтрам</td>';
        document.getElementById('requests-tbody').appendChild(emptyRow);
      }
      emptyRow.style.display = '';
    } else if (emptyRow) {
      emptyRow.style.display = 'none';
    }
  }

  // ── Управление активностью chip-кнопок ──────────────────────────────────
  function setActiveChip(group, value) {
    const chips = document.querySelectorAll(
      '.chip-filterbar [data-chip-group="' + group + '"]'
    );
    chips.forEach(function (c) {
      const isActive = c.dataset.chipValue === value;
      c.classList.toggle('chip-active', isActive);
      // Bootstrap-стили
      const base = c.dataset.chipBase || 'secondary';
      if (isActive) {
        c.classList.remove('btn-outline-' + base);
        c.classList.add('btn-' + base);
      } else {
        c.classList.remove('btn-' + base);
        c.classList.add('btn-outline-' + base);
      }
    });
  }

  // ── Привязка кликов на chips ─────────────────────────────────────────────
  function bindChips() {
    document.querySelectorAll('.chip-filterbar [data-chip-group]').forEach(function (chip) {
      chip.addEventListener('click', function (e) {
        e.preventDefault();
        const group = chip.dataset.chipGroup;
        const value = chip.dataset.chipValue;

        // Toggle: повторный клик снимает фильтр
        if (state[group] === value) {
          state[group] = null;
          setActiveChip(group, null);
        } else {
          state[group] = value;
          setActiveChip(group, value);
        }

        applyFilters();
      });
    });

    // Кнопка «Сбросить всё»
    const resetBtn = document.getElementById('chip-reset-all');
    if (resetBtn) {
      resetBtn.addEventListener('click', function (e) {
        e.preventDefault();
        state.status = null;
        state.employee = null;
        state.date = null;
        ['status', 'employee', 'date'].forEach(function (g) {
          setActiveChip(g, null);
        });
        applyFilters();
      });
    }
  }

  // ── Инициализация ────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {
    if (!document.getElementById('requests-tbody')) return;
    bindChips();
    applyFilters();
  });

})();
