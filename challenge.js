(function () {
  const progressKey = 'armyriot:location-progress';
  const form = document.querySelector('[data-challenge-form]');

  if (!form) {
    return;
  }

  const body = document.body;
  const stage = Number.parseInt(body.dataset.stage || '1', 10);
  const requiredStage = Math.max(0, stage - 1);
  const nextUrl = body.dataset.next || 'index.html';
  const answer = normalize(body.dataset.answer || '');
  const successMessage = body.dataset.success || 'Correct. Continue to the next location.';
  const blockedMessage = body.dataset.blocked || 'Complete the previous location first.';

  const input = form.querySelector('input');
  const submitButton = form.querySelector('button[type="submit"]');
  const result = document.querySelector('[data-result]');
  const lockNote = document.querySelector('[data-lock-note]');

  function normalize(value) {
    return value.trim().toLowerCase();
  }

  function getProgress() {
    const raw = Number.parseInt(localStorage.getItem(progressKey) || '0', 10);
    if (!Number.isFinite(raw) || raw < 0) {
      return 0;
    }

    return raw;
  }

  function setProgress(value) {
    localStorage.setItem(progressKey, String(value));
  }

  function setResult(message, variant) {
    if (!result) {
      return;
    }

    result.textContent = message;
    result.classList.remove('success', 'error');
    if (variant) {
      result.classList.add(variant);
    }
  }

  function blockChallenge() {
    if (getProgress() >= requiredStage) {
      return false;
    }

    if (lockNote) {
      lockNote.textContent = blockedMessage;
    }
    if (input) {
      input.disabled = true;
    }
    if (submitButton) {
      submitButton.disabled = true;
    }
    setResult(blockedMessage, 'error');
    return true;
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();

    if (blockChallenge()) {
      return;
    }

    const guess = normalize(input.value);
    if (!guess) {
      setResult('Enter an answer before continuing.', 'error');
      input.focus();
      return;
    }

    if (guess !== answer) {
      setResult('That answer is not correct. Try again.', 'error');
      input.focus();
      input.select();
      return;
    }

    setProgress(Math.max(getProgress(), stage));
    setResult(successMessage, 'success');
    input.disabled = true;
    submitButton.disabled = true;

    window.setTimeout(() => {
      window.location.href = nextUrl;
    }, 1100);
  });

  blockChallenge();
})();