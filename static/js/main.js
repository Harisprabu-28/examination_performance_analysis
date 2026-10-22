/**
 * Examination Performance Analysis System
 * JavaScript Interactive Controls & Chart.js Visualizations
 */

document.addEventListener('DOMContentLoaded', function () {
  // 1. Mobile Sidebar Toggle
  const toggleBtn = document.getElementById('sidebarToggle');
  const sidebar = document.querySelector('.sidebar');
  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', function () {
      sidebar.classList.toggle('show');
    });
  }

  // 2. Initialize Real-time Marks Calculation if Add/Edit Marks Form is present
  initLiveMarksCalculator();

  // 3. Initialize Live Search Filters on Tables
  initTableSearch();
});

/**
 * Real-time Marks Calculation & Preview
 */
function initLiveMarksCalculator() {
  const mathInput = document.getElementById('math_input');
  const engInput = document.getElementById('eng_input');
  const sciInput = document.getElementById('sci_input');
  const csInput = document.getElementById('cs_input');
  const dbInput = document.getElementById('db_input');
  const webInput = document.getElementById('web_input');

  if (!mathInput || !engInput || !sciInput || !csInput || !dbInput || !webInput) {
    return;
  }

  const inputs = [mathInput, engInput, sciInput, csInput, dbInput, webInput];

  function updateMetrics() {
    let total = 0;
    let anyFail = false;
    let allValid = true;

    inputs.forEach(input => {
      let val = parseFloat(input.value);
      if (isNaN(val)) {
        val = 0;
        allValid = false;
      }
      if (val < 0) val = 0;
      if (val > 100) val = 100;
      if (val < 40) anyFail = true;
      total += val;
    });

    const average = total / 6.0;
    const percentage = (total / 600.0) * 100.0;

    let grade = 'F';
    if (percentage >= 90) grade = 'A+';
    else if (percentage >= 80) grade = 'A';
    else if (percentage >= 70) grade = 'B+';
    else if (percentage >= 60) grade = 'B';
    else if (percentage >= 50) grade = 'C';
    else if (percentage >= 40) grade = 'D';
    else grade = 'F';

    const result = anyFail || percentage < 40 ? 'FAIL' : 'PASS';

    // Update UI elements
    const totalEl = document.getElementById('calc_total');
    const avgEl = document.getElementById('calc_avg');
    const percEl = document.getElementById('calc_perc');
    const gradeEl = document.getElementById('calc_grade');
    const resultEl = document.getElementById('calc_result');

    if (totalEl) totalEl.textContent = total.toFixed(1);
    if (avgEl) avgEl.textContent = average.toFixed(2);
    if (percEl) percEl.textContent = percentage.toFixed(2) + '%';
    if (gradeEl) gradeEl.textContent = grade;
    if (resultEl) {
      resultEl.textContent = result;
      resultEl.className = 'badge-custom ' + (result === 'PASS' ? 'badge-pass' : 'badge-fail');
    }
  }

  inputs.forEach(input => {
    input.addEventListener('input', updateMetrics);
  });

  // Trigger initial calculation
  updateMetrics();
}

/**
 * Universal Client-side Table Filter
 */
function initTableSearch() {
  const searchInput = document.getElementById('tableSearchInput');
  const table = document.getElementById('dataTable');
  if (!searchInput || !table) return;

  searchInput.addEventListener('keyup', function () {
    const filter = searchInput.value.toLowerCase();
    const rows = table.getElementsByTagName('tbody')[0].getElementsByTagName('tr');

    for (let i = 0; i < rows.length; i++) {
      const text = rows[i].textContent.toLowerCase();
      if (text.indexOf(filter) > -1) {
        rows[i].style.display = '';
      } else {
        rows[i].style.display = 'none';
      }
    }
  });
}

/**
 * Chart.js Helpers
 */
window.ExamCharts = {
  // 1. Subject Averages Bar Chart
  renderSubjectBarChart: function (canvasId, labels, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    return new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Class Average Marks (/100)',
          data: data,
          backgroundColor: [
            'rgba(37, 99, 235, 0.85)',
            'rgba(59, 130, 246, 0.85)',
            'rgba(16, 185, 129, 0.85)',
            'rgba(139, 92, 246, 0.85)',
            'rgba(245, 158, 11, 0.85)',
            'rgba(6, 182, 212, 0.85)'
          ],
          borderRadius: 8,
          borderWidth: 0,
          maxBarThickness: 45
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0f172a',
            padding: 10,
            cornerRadius: 8
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            max: 100,
            grid: { color: 'rgba(226, 232, 240, 0.8)' }
          },
          x: {
            grid: { display: false }
          }
        }
      }
    });
  },

  // 2. Pass vs Fail Pie Chart
  renderPassFailPieChart: function (canvasId, passCount, failCount) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    return new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Passed', 'Failed'],
        datasets: [{
          data: [passCount, failCount],
          backgroundColor: ['#10b981', '#ef4444'],
          hoverOffset: 6,
          borderWidth: 2,
          borderColor: '#ffffff'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '70%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: { boxWidth: 14, padding: 15, font: { weight: '600' } }
          }
        }
      }
    });
  },

  // 3. Grade Distribution Doughnut Chart
  renderGradeChart: function (canvasId, gradeCounts) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    const labels = Object.keys(gradeCounts);
    const values = Object.values(gradeCounts);

    return new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: labels,
        datasets: [{
          data: values,
          backgroundColor: [
            '#10b981', // A+
            '#3b82f6', // A
            '#6366f1', // B+
            '#8b5cf6', // B
            '#f59e0b', // C
            '#ea580c', // D
            '#ef4444'  // F
          ],
          hoverOffset: 6,
          borderWidth: 2,
          borderColor: '#ffffff'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '65%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: { boxWidth: 12, padding: 10, font: { size: 11, weight: '600' } }
          }
        }
      }
    });
  },

  // 4. Performance Trend Line Chart
  renderTrendLineChart: function (canvasId, examLabels, avgScores, topScores) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    return new Chart(ctx, {
      type: 'line',
      data: {
        labels: examLabels,
        datasets: [
          {
            label: 'Batch Average (%)',
            data: avgScores,
            borderColor: '#2563eb',
            backgroundColor: 'rgba(37, 99, 235, 0.1)',
            fill: true,
            tension: 0.3,
            borderWidth: 3,
            pointRadius: 5
          },
          {
            label: 'Highest Score (%)',
            data: topScores,
            borderColor: '#10b981',
            backgroundColor: 'transparent',
            borderDash: [5, 5],
            tension: 0.3,
            borderWidth: 2,
            pointRadius: 5
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'top' }
        },
        scales: {
          y: {
            beginAtZero: false,
            min: 40,
            max: 100,
            grid: { color: 'rgba(226, 232, 240, 0.8)' }
          },
          x: { grid: { display: false } }
        }
      }
    });
  },

  // 5. Radar Chart for Individual Student
  renderStudentRadarChart: function (canvasId, studentScores) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    const subjects = ['Mathematics', 'English', 'Science', 'Computer Science', 'Database Management', 'Web Technology'];

    return new Chart(ctx, {
      type: 'radar',
      data: {
        labels: subjects,
        datasets: [
          {
            label: 'Student Marks',
            data: studentScores,
            backgroundColor: 'rgba(37, 99, 235, 0.25)',
            borderColor: '#2563eb',
            pointBackgroundColor: '#2563eb',
            pointBorderColor: '#fff',
            pointHoverBackgroundColor: '#fff',
            pointHoverBorderColor: '#2563eb',
            borderWidth: 2
          },
          {
            label: 'Passing Benchmark (40)',
            data: [40, 40, 40, 40, 40, 40],
            borderColor: 'rgba(239, 68, 68, 0.6)',
            borderDash: [4, 4],
            backgroundColor: 'transparent',
            pointRadius: 0,
            borderWidth: 1.5
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          r: {
            angleLines: { color: 'rgba(226, 232, 240, 0.8)' },
            grid: { color: 'rgba(226, 232, 240, 0.8)' },
            suggestedMin: 0,
            suggestedMax: 100,
            ticks: { stepSize: 20 }
          }
        }
      }
    });
  }
};

/**
 * ==============================================================================
 * Study Planner & Notification System (Modules 4 & 5)
 * ==============================================================================
 */
document.addEventListener('DOMContentLoaded', function () {
  initNotificationBell();
});

function initNotificationBell() {
  const bellBtn = document.getElementById('notificationBell');
  const panel = document.getElementById('notificationPanel');
  const markAllBtn = document.getElementById('markAllReadBtn');

  if (!bellBtn || !panel) return;

  // Toggle dropdown on click
  bellBtn.addEventListener('click', function (e) {
    e.stopPropagation();
    const isOpen = panel.classList.contains('show');
    if (!isOpen) {
      loadNotifications();
      panel.classList.add('show');
    } else {
      panel.classList.remove('show');
    }
  });

  // Close when clicking outside
  document.addEventListener('click', function (e) {
    if (!panel.contains(e.target) && e.target !== bellBtn && !bellBtn.contains(e.target)) {
      panel.classList.remove('show');
    }
  });

  // Mark all as read
  if (markAllBtn) {
    markAllBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      fetch('/api/notifications/read-all', { method: 'POST' })
        .then(res => res.json())
        .then(() => {
          const badge = document.getElementById('notifBadge');
          if (badge) badge.remove();
          loadNotifications();
        })
        .catch(err => console.error(err));
    });
  }

  // Periodic poll for unread notifications every 45s
  setInterval(pollNotificationBadge, 45000);
}

function loadNotifications() {
  const listEl = document.getElementById('notificationList');
  if (!listEl) return;

  listEl.innerHTML = '<div class="text-center text-muted py-4"><i class="fa-solid fa-spinner fa-spin"></i> Loading...</div>';

  fetch('/api/notifications')
    .then(res => res.json())
    .then(data => {
      if (data.status === 'success' && data.notifications) {
        renderNotificationList(data.notifications, data.unread_count);
      } else {
        listEl.innerHTML = '<div class="text-center text-muted py-4 small">No notifications found</div>';
      }
    })
    .catch(err => {
      console.error(err);
      listEl.innerHTML = '<div class="text-center text-danger py-4 small">Error loading notifications</div>';
    });
}

function renderNotificationList(notifications, unreadCount) {
  const listEl = document.getElementById('notificationList');
  if (!listEl) return;

  // Update badge
  updateBadgeDisplay(unreadCount);

  if (notifications.length === 0) {
    listEl.innerHTML = `
      <div class="text-center py-5 text-muted">
        <i class="fa-regular fa-bell-slash fs-3 mb-2 opacity-50"></i>
        <div class="small fw-semibold">No notifications right now</div>
        <div class="text-xs text-muted" style="font-size: 0.72rem;">You are caught up with your study timetable!</div>
      </div>
    `;
    return;
  }

  let html = '';
  notifications.forEach(n => {
    const isUnread = n.is_read === 0;
    const typeClass = n.notification_type === 'alert' ? 'alert' : 'reminder';
    const iconClass = n.notification_type === 'alert' ? 'fa-solid fa-triangle-exclamation' : 'fa-solid fa-clock';

    html += `
      <div class="notification-item ${isUnread ? 'unread' : ''}" onclick="onNotificationClick(${n.id})">
        <div class="notification-icon-box ${typeClass}">
          <i class="${iconClass}"></i>
        </div>
        <div class="notification-item-content">
          <div class="notification-item-title">${escapeHtml(n.title)}</div>
          <div class="notification-item-msg">${escapeHtml(n.message)}</div>
          <div class="notification-item-time">${escapeHtml(n.created_at || '')}</div>
        </div>
        ${isUnread ? '<span class="badge bg-primary rounded-pill p-1" style="font-size: 0.5rem;">•</span>' : ''}
      </div>
    `;
  });

  listEl.innerHTML = html;
}

function onNotificationClick(notifId) {
  fetch(`/api/notifications/${notifId}/read`, { method: 'POST' })
    .then(res => res.json())
    .then(() => {
      // Reload list and badge
      loadNotifications();
    })
    .catch(err => console.error(err));
}

function pollNotificationBadge() {
  fetch('/api/notifications')
    .then(res => res.json())
    .then(data => {
      if (data.status === 'success') {
        updateBadgeDisplay(data.unread_count);
      }
    })
    .catch(err => console.debug('Polling notification count skipped:', err));
}

function updateBadgeDisplay(count) {
  const bellBtn = document.getElementById('notificationBell');
  let badge = document.getElementById('notifBadge');

  if (count > 0) {
    if (!badge && bellBtn) {
      badge = document.createElement('span');
      badge.id = 'notifBadge';
      badge.className = 'notification-badge';
      bellBtn.appendChild(badge);
    }
    if (badge) badge.textContent = count;
  } else {
    if (badge) badge.remove();
  }
}

function escapeHtml(text) {
  if (!text) return '';
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return String(text).replace(/[&<>"']/g, m => map[m]);
}

/**
 * Universal study session status updater
 */
window.updateSessionStatus = function (sessionId, status) {
  fetch(`/api/study-planner/session/${sessionId}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: status })
  })
    .then(res => res.json())
    .then(data => {
      if (data.status === 'success') {
        window.location.reload();
      } else {
        alert(data.message || 'Error updating session status.');
      }
    })
    .catch(err => {
      console.error(err);
      alert('Network error updating session.');
    });
};

