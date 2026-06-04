document.addEventListener('DOMContentLoaded', async () => {
    const grid = document.getElementById('grid');
    const queryDisplay = document.getElementById('query-display');
    const toast = document.getElementById('toast');

    const resp = await fetch('/api/candidates');
    const data = await resp.json();

    queryDisplay.textContent = `Query: "${data.query}" — ${data.candidates.length} candidates`;

    data.candidates.forEach((c, i) => {
        const card = document.createElement('div');
        card.className = 'card';
        card.dataset.id = c.id;

        const licenseClass = ['unknown', 'copyrighted'].includes(c.license) ? 'risky' : '';

        card.innerHTML = `
            <img class="card-img" src="${c.url}" alt="${c.title || ''}" loading="lazy"
                 onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22280%22 height=%22210%22><rect fill=%22%23222%22 width=%22280%22 height=%22210%22/><text x=%2250%25%22 y=%2250%25%22 fill=%22%23666%22 text-anchor=%22middle%22 dy=%22.3em%22 font-size=%2214%22>Failed to load</text></svg>'">
            <div class="card-body">
                <div class="card-title">${c.title || c.url.split('/').pop() || `#${i + 1}`}</div>
                <div class="card-scores">
                    ${c.scores.relevance ? `<span class="badge badge-relevance">rel ${c.scores.relevance.toFixed(2)}</span>` : ''}
                    ${c.scores.aesthetic ? `<span class="badge badge-aesthetic">aes ${c.scores.aesthetic.toFixed(1)}</span>` : ''}
                    ${c.scores.vision ? `<span class="badge badge-vision">vis ${c.scores.vision.toFixed(1)}</span>` : ''}
                    <span class="badge badge-composite">score ${c.scores.composite.toFixed(3)}</span>
                </div>
                <div class="card-meta">
                    <span>${c.source} ${c.width && c.height ? `· ${c.width}×${c.height}` : ''}</span>
                    <span class="license-tag ${licenseClass}">${c.license}</span>
                </div>
            </div>
        `;

        card.addEventListener('click', async () => {
            const pickResp = await fetch(`/api/pick/${c.id}`, { method: 'POST' });
            if (pickResp.ok) {
                document.querySelectorAll('.card').forEach(el => el.classList.remove('picked'));
                card.classList.add('picked');
                showToast(`Picked: ${c.title || c.id}`);
            }
        });

        grid.appendChild(card);
    });

    function showToast(msg) {
        toast.textContent = msg;
        toast.classList.remove('hidden');
        setTimeout(() => toast.classList.add('hidden'), 2000);
    }

    document.addEventListener('keydown', (e) => {
        const num = parseInt(e.key);
        if (num >= 1 && num <= 9) {
            const cards = document.querySelectorAll('.card');
            if (cards[num - 1]) cards[num - 1].click();
        }
    });
});
