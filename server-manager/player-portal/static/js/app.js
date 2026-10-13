// Auto-refresh player status every 30 seconds
(function () {
  const REFRESH_INTERVAL = 30000;

  function buildPlayerList(data) {
    if (data.online && data.players.length > 0) {
      return '<ul class="player-list">' +
        data.players.map(p =>
          `<li class="player-item">
            <img src="https://mc-heads.net/avatar/${p}/32" width="32" height="32"
                 class="player-avatar" alt="${p}"
                 onerror="this.src='https://mc-heads.net/avatar/Steve/32'">
            <span class="player-name">${p}</span>
          </li>`
        ).join('') +
        '</ul>';
    } else if (data.online) {
      return '<div class="empty-state"><i class="bi bi-moon-stars"></i><p>No players online right now.</p></div>';
    } else {
      return '<div class="empty-state empty-state--danger"><i class="bi bi-plug-fill"></i><p>Server is offline.</p></div>';
    }
  }

  function updateStatus() {
    fetch('/api/status')
      .then(r => r.json())
      .then(data => {
        const hero     = document.querySelector('.hero');
        const badge    = document.querySelector('.status-badge');
        const badgeDot = document.querySelector('.status-badge-dot');
        const glow     = document.querySelector('.hero-glow');
        const count    = document.getElementById('player-count');
        const list     = document.getElementById('players-list');

        const online = data.online;

        if (hero) {
          hero.classList.toggle('hero--online',  online);
          hero.classList.toggle('hero--offline', !online);
        }
        if (badge) {
          badge.classList.toggle('status-badge--online',  online);
          badge.classList.toggle('status-badge--offline', !online);
          badge.querySelector('span:last-child').textContent = online ? 'Online' : 'Offline';
        }
        if (count) count.textContent = data.player_count || 0;
        if (list)  list.innerHTML = buildPlayerList(data);
      })
      .catch(() => {});
  }

  if (document.querySelector('.hero')) {
    setInterval(updateStatus, REFRESH_INTERVAL);
  }
})();
