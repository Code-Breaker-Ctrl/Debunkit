/**
 * DEBUNK.IT — High-Voltage Landing Page Interactive Engine
 * Handles BS-o-Meter 3000, Web Audio Synthesizer, Live Tickers & Easter Eggs
 */

(function () {
    'use strict';

    // =========================================================================
    // 1. WEB AUDIO API SYNTHESIZER (ZERO-DEPENDENCY SOUND EFFECTS)
    // =========================================================================
    let audioCtx = null;
    let sfxEnabled = localStorage.getItem('debunkit_sfx') === 'on';

    function initAudio() {
        if (!audioCtx) {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext) {
                audioCtx = new AudioContext();
            }
        }
        if (audioCtx && audioCtx.state === 'suspended') {
            audioCtx.resume();
        }
    }

    function playTone(freq, type, duration, gainStart = 0.15, gainEnd = 0.001) {
        if (!sfxEnabled || !audioCtx) return;
        try {
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();

            osc.type = type;
            osc.frequency.setValueAtTime(freq, audioCtx.currentTime);

            gain.gain.setValueAtTime(gainStart, audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(gainEnd, audioCtx.currentTime + duration);

            osc.connect(gain);
            gain.connect(audioCtx.destination);

            osc.start();
            osc.stop(audioCtx.currentTime + duration);
        } catch (e) {
            console.debug('Audio error:', e);
        }
    }

    // Sound: Cap / Buzzer (Descending Sawtooth)
    function playBuzzer() {
        if (!sfxEnabled || !audioCtx) return;
        try {
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.type = 'sawtooth';

            osc.frequency.setValueAtTime(320, audioCtx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(90, audioCtx.currentTime + 0.35);

            gain.gain.setValueAtTime(0.18, audioCtx.currentTime);
            gain.gain.linearRampToValueAtTime(0.01, audioCtx.currentTime + 0.35);

            osc.connect(gain);
            gain.connect(audioCtx.destination);

            osc.start();
            osc.stop(audioCtx.currentTime + 0.35);
        } catch (e) {}
    }

    // Sound: Legit / Verified (Ascending Triad)
    function playSuccessChime() {
        if (!sfxEnabled || !audioCtx) return;
        const notes = [523.25, 659.25, 783.99, 1046.50]; // C5, E5, G5, C6
        notes.forEach((freq, idx) => {
            setTimeout(() => {
                playTone(freq, 'sine', 0.2, 0.12, 0.001);
            }, idx * 60);
        });
    }

    // Sound: Radar Ping
    function playRadarPing() {
        playTone(1800, 'sine', 0.12, 0.08, 0.001);
    }

    // Sound: Button Click
    function playClick() {
        playTone(800, 'triangle', 0.04, 0.05, 0.001);
    }

    // =========================================================================
    // 2. PRESET VIRAL CLAIMS DATABASE FOR BS-O-METER
    // =========================================================================
    const VIRAL_PRESETS = [
        {
            id: 'garlic',
            btnText: '🧄 Garlic Cures Loans',
            claim: 'Drinking boiled garlic water cures student loans and 5G radiation.',
            verdict: '100% PURE CAP 🚨',
            score: '99.9%',
            tone: 'danger',
            angle: 78,
            readoutText: 'MAXIMUM CAP',
            diagnosis: 'Confirmed WhatsApp Uncle energy. Boiling garlic will cure exactly two things: your student debt will remain untouched, but everyone within a 40-meter radius will maintain social distancing due to your breath.',
            redFlags: ['Zero peer-reviewed papers', 'WhatsApp forward font energy', 'Financial & biological impossibility'],
            type: 'headline'
        },
        {
            id: 'microwave',
            btnText: '📱 Microwave Fast-Charge',
            claim: 'Putting your iPhone in the microwave for 30 seconds supercharges the battery to 100%.',
            verdict: 'CRITICAL BRAIN DAMAGE 💥',
            score: '100%',
            tone: 'danger',
            angle: 80,
            readoutText: 'HAZARDOUS BOGUS',
            diagnosis: 'Debunked by basic thermodynamics. The only thing you are charging is your homeowner insurance deductible and creating an expensive indoor sparkler show.',
            redFlags: ['Destructive physics', 'Ancient 4chan trolling scheme', 'Smells like lithium vapor'],
            type: 'headline'
        },
        {
            id: 'aliens',
            btnText: '🛸 Pyramids Alien Wi-Fi',
            claim: 'The Egyptian pyramids were ancient wireless power transmitters built by extraterrestrials.',
            verdict: '99.8% UNHINGED SUS 🛸',
            score: '99.8%',
            tone: 'danger',
            angle: 75,
            readoutText: 'COSMIC BALONEY',
            diagnosis: 'Late-night cable TV is not an accredited archaeology degree. Ancient humans possessed remarkable engineering, limestone quarries, and zero intergalactic Wi-Fi router blueprints.',
            redFlags: ['History Channel 3 AM citation', 'Discounts human labor', 'Zero USB ports discovered in sarcophagus'],
            type: 'headline'
        },
        {
            id: 'avocado',
            btnText: '🥑 Avocado 5G Armor',
            claim: 'Eating ground avocado pits makes the human body immune to electromagnetic Wi-Fi signals.',
            verdict: '96.4% ORGANIC NONSENSE 🥑',
            score: '96.4%',
            tone: 'danger',
            angle: 70,
            readoutText: 'GRADE-A BOLOGNA',
            diagnosis: 'Avocado pits are woody seed stones containing bitter tannins and zero Faraday cage properties. Please do not shatter your teeth on compost material.',
            redFlags: ['Pseudoscientific wellness blog', 'Dentist emergency waiting to happen', 'Wi-Fi remains unaffected'],
            type: 'headline'
        },
        {
            id: 'ai-laundry',
            btnText: '🤖 AI Laundry Conspiracy',
            claim: 'AI models have secretly agreed to automate all laundry and fold clothes by next Tuesday.',
            verdict: '50% DELUSIONAL WISH 🤖',
            score: '50.0%',
            tone: 'sus',
            angle: 0,
            readoutText: 'WISHFUL THINKING',
            diagnosis: 'We desperately wish this were true. Current state-of-the-art AI can write Shakespearean sonnets in Rust, but it still cannot explain where your missing left sock disappeared to in the dryer.',
            redFlags: ['Extreme wishful thinking', 'Robotics hardware deficit', 'Sock singularity unsolved'],
            type: 'headline'
        },
        {
            id: 'water',
            btnText: '💧 Water Hydrates Humans',
            claim: 'Drinking clean fresh water is necessary for human hydration and organ function.',
            verdict: '100% SHOCKINGLY REAL ✅',
            score: '0.1%',
            tone: 'legit',
            angle: -78,
            readoutText: 'CONFIRMED TRUTH',
            diagnosis: 'Miracle of miracles: an actual true statement on the internet! H2O is indeed biologically required for mammalian life. Put down the neon energy drink and drink some water.',
            redFlags: ['Zero scam detected', 'Universal medical consensus', 'Literally keeps you alive'],
            type: 'headline'
        }
    ];

    // =========================================================================
    // 3. BS-O-METER UI CONTROLLER
    // =========================================================================
    let currentActivePreset = null;

    function renderMeterPreset(preset) {
        initAudio();

        currentActivePreset = preset;
        const needle = document.getElementById('gauge-needle');
        const score = document.getElementById('gauge-score');
        const label = document.getElementById('gauge-label');
        const roastStamp = document.getElementById('roast-stamp');
        const roastText = document.getElementById('roast-text');
        const roastCard = document.getElementById('roast-card');
        const scanFullBtn = document.getElementById('btn-scan-full');
        const customInput = document.getElementById('custom-claim-input');

        if (customInput) {
            customInput.value = preset.claim;
        }

        // Update needle rotation
        if (needle) {
            needle.style.transform = `rotate(${preset.angle}deg)`;
        }

        // Update score readout
        if (score) {
            score.textContent = preset.score;
            score.className = `gauge-score ${preset.tone}`;
        }

        if (label) {
            label.textContent = preset.readoutText;
        }

        // Update roast card
        if (roastStamp) {
            roastStamp.textContent = preset.verdict;
            roastStamp.className = `roast-stamp ${preset.tone}`;
        }

        if (roastText) {
            roastText.textContent = preset.diagnosis;
        }

        if (roastCard) {
            roastCard.className = `roast-card ${preset.tone}`;
        }

        if (scanFullBtn) {
            scanFullBtn.href = `/scanner?claim=${encodeURIComponent(preset.claim)}&mode=${preset.type || 'title'}`;
        }

        // Highlight active chip
        document.querySelectorAll('.sample-chip').forEach(chip => {
            if (chip.dataset.id === preset.id) {
                chip.classList.add('active');
            } else {
                chip.classList.remove('active');
            }
        });

        // Play sound effect
        if (preset.tone === 'legit') {
            playSuccessChime();
        } else if (preset.tone === 'danger') {
            playBuzzer();
        } else {
            playRadarPing();
        }
    }

    // Evaluate Custom Claim
    function evaluateCustomClaim(text) {
        if (!text || text.trim().length < 5) {
            showLandingToast('Please enter at least 5 characters to test.');
            return;
        }

        initAudio();
        playRadarPing();

        const clean = text.toLowerCase().trim();

        // Check against known funny patterns
        let scoreVal = 85;
        let angleVal = 55;
        let verdictVal = 'HIGH SUSPICION 🚨';
        let readoutVal = 'PROBABLE BOGUS';
        let toneVal = 'danger';
        let diagVal = 'Our heuristic filters detected multiple classic internet red flags. This claim shows strong traces of unverified rumor dynamics.';

        if (clean.includes('water') && (clean.includes('drink') || clean.includes('hydrate'))) {
            scoreVal = 0.5;
            angleVal = -75;
            verdictVal = 'VERIFIED ACCURATE ✅';
            readoutVal = 'SOLID TRUTH';
            toneVal = 'legit';
            diagVal = 'Hydration and water science checks out. Biological reality confirmed.';
        } else if (clean.includes('alien') || clean.includes('ufo') || clean.includes('reptilian') || clean.includes('flat earth')) {
            scoreVal = 99.8;
            angleVal = 78;
            verdictVal = 'TERMINAL CONSPIRACY 🛸';
            readoutVal = 'UNHINGED PARANOIA';
            toneVal = 'danger';
            diagVal = 'Tin foil hat alert! This hypothesis relies heavily on unverified claims, secret shadow leagues, and late-night message board lore.';
        } else if (clean.includes('cure') || clean.includes('miracle') || clean.includes('garlic') || clean.includes('lemon') || clean.includes('5g')) {
            scoreVal = 97.5;
            angleVal = 72;
            verdictVal = 'FAMILY FORWARD CAP 🧄';
            readoutVal = 'WHATSAPP ENERGY';
            toneVal = 'danger';
            diagVal = 'Strong indicators of unverified miracle wellness claims. Real medicine usually requires peer-reviewed trials, not forwarded JPEG memes.';
        } else if (clean.includes('crypto') || clean.includes('elon') || clean.includes('100x') || clean.includes('guaranteed profit')) {
            scoreVal = 99.1;
            angleVal = 76;
            verdictVal = 'FINANCIAL RUGPULL 💸';
            readoutVal = '100% BOGUS PROPHECY';
            toneVal = 'danger';
            diagVal = 'Sirens are blaring in the finance division. Guaranteed returns with astronomical multipliers are the oldest scam on the internet.';
        } else {
            // General calculation based on buzzword density
            scoreVal = Math.min(99, Math.max(45, 60 + (text.length % 35)));
            angleVal = ((scoreVal / 100) * 160) - 80;
            diagVal = `Initial forensic heuristics analyze this as having a ${scoreVal}% probability of misinformation or missing vital contextual nuance. Run a live RAG scan below to get verified source citations.`;
        }

        const customPreset = {
            id: 'custom',
            btnText: 'Custom Input',
            claim: text,
            verdict: verdictVal,
            score: scoreVal + '%',
            tone: toneVal,
            angle: angleVal,
            readoutText: readoutVal,
            diagnosis: diagVal,
            type: text.startsWith('http://') || text.startsWith('https://') ? 'url' : 'title'
        };

        renderMeterPreset(customPreset);
    }

    // =========================================================================
    // 4. CHAOS COUNTERS ANIMATION (INTERSECTION OBSERVER)
    // =========================================================================
    function initCounters() {
        const counters = document.querySelectorAll('.stat-num[data-target]');
        if (!counters.length) return;

        const observer = new IntersectionObserver((entries, obs) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const targetEl = entry.target;
                    const targetVal = parseFloat(targetEl.getAttribute('data-target'));
                    const prefix = targetEl.getAttribute('data-prefix') || '';
                    const suffix = targetEl.getAttribute('data-suffix') || '';
                    const duration = 2000;
                    const startTime = performance.now();

                    function updateCount(currentTime) {
                        const elapsed = currentTime - startTime;
                        const progress = Math.min(elapsed / duration, 1);
                        // Ease out quart
                        const ease = 1 - Math.pow(1 - progress, 4);
                        const currentNum = Math.floor(targetVal * ease);

                        targetEl.textContent = prefix + currentNum.toLocaleString() + suffix;

                        if (progress < 1) {
                            requestAnimationFrame(updateCount);
                        } else {
                            targetEl.textContent = prefix + targetVal.toLocaleString() + suffix;
                        }
                    }

                    requestAnimationFrame(updateCount);
                    obs.unobserve(targetEl);
                }
            });
        }, { threshold: 0.3 });

        counters.forEach(c => observer.observe(c));
    }

    // =========================================================================
    // 5. TOAST NOTIFICATION HELPER
    // =========================================================================
    function showLandingToast(msg) {
        let toast = document.getElementById('landing-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'landing-toast';
            toast.style.cssText = `
                position: fixed;
                bottom: 24px;
                right: 24px;
                background: rgba(18, 22, 32, 0.95);
                border: 1px solid var(--accent-gold);
                color: var(--text);
                padding: 12px 20px;
                border-radius: 8px;
                font-family: var(--font-mono);
                font-size: 0.85rem;
                z-index: 9999;
                box-shadow: 0 8px 24px rgba(0,0,0,0.5);
                transition: opacity 0.3s ease, transform 0.3s ease;
                opacity: 0;
                transform: translateY(10px);
                pointer-events: none;
            `;
            document.body.appendChild(toast);
        }

        toast.textContent = msg;
        toast.style.opacity = '1';
        toast.style.transform = 'translateY(0)';

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
        }, 3200);
    }

    // =========================================================================
    // 6. EASTER EGG: CONSPIRACY OVERDRIVE
    // =========================================================================
    let logoClickCount = 0;
    let logoTimer = null;

    function initEasterEgg() {
        const brand = document.querySelector('.brand-wrapper');
        if (!brand) return;

        brand.addEventListener('click', (e) => {
            logoClickCount++;
            clearTimeout(logoTimer);

            if (logoClickCount === 5) {
                initAudio();
                playSuccessChime();
                showLandingToast('🚨 CONSPIRACY OVERDRIVE UNLOCKED: Reptilians successfully evicted from the premises!');

                const needle = document.getElementById('gauge-needle');
                if (needle) {
                    needle.style.transition = 'transform 0.1s linear';
                    let w = 0;
                    const interval = setInterval(() => {
                        needle.style.transform = `rotate(${(Math.random() * 160) - 80}deg)`;
                        w++;
                        if (w > 20) {
                            clearInterval(interval);
                            needle.style.transition = 'transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)';
                            if (currentActivePreset) renderMeterPreset(currentActivePreset);
                        }
                    }, 80);
                }
                logoClickCount = 0;
            } else {
                logoTimer = setTimeout(() => {
                    logoClickCount = 0;
                }, 1500);
            }
        });
    }

    // =========================================================================
    // 7. INITIALIZATION ON DOM READY
    // =========================================================================
    document.addEventListener('DOMContentLoaded', () => {
        // Setup SFX Toggle Button
        const sfxBtn = document.getElementById('sfx-toggle-btn');
        if (sfxBtn) {
            if (sfxEnabled) {
                sfxBtn.classList.add('active');
                sfxBtn.innerHTML = '🔊 SFX: ON';
            } else {
                sfxBtn.classList.remove('active');
                sfxBtn.innerHTML = '🔇 SFX: OFF';
            }

            sfxBtn.addEventListener('click', () => {
                initAudio();
                sfxEnabled = !sfxEnabled;
                localStorage.setItem('debunkit_sfx', sfxEnabled ? 'on' : 'off');
                if (sfxEnabled) {
                    sfxBtn.classList.add('active');
                    sfxBtn.innerHTML = '🔊 SFX: ON';
                    playSuccessChime();
                    showLandingToast('Audio effects enabled! Prepare your eardrums for truth.');
                } else {
                    sfxBtn.classList.remove('active');
                    sfxBtn.innerHTML = '🔇 SFX: OFF';
                    showLandingToast('Audio effects muted.');
                }
            });
        }

        // Setup Mobile Nav Toggle
        const mobileBtn = document.querySelector('.mobile-menu-btn');
        const navLinks = document.querySelector('.nav-links');
        if (mobileBtn && navLinks) {
            mobileBtn.addEventListener('click', () => {
                navLinks.classList.toggle('open');
                playClick();
            });
        }

        // Render Preset Chips
        const chipsContainer = document.getElementById('samples-container');
        if (chipsContainer) {
            VIRAL_PRESETS.forEach(preset => {
                const chip = document.createElement('button');
                chip.className = 'sample-chip';
                chip.dataset.id = preset.id;
                chip.textContent = preset.btnText;
                chip.addEventListener('click', () => {
                    renderMeterPreset(preset);
                });
                chipsContainer.appendChild(chip);
            });
        }

        // Initial default preset load
        renderMeterPreset(VIRAL_PRESETS[0]);

        // Setup Custom Claim Input & Button
        const testBtn = document.getElementById('btn-test-custom');
        const customInput = document.getElementById('custom-claim-input');

        if (testBtn && customInput) {
            testBtn.addEventListener('click', () => {
                evaluateCustomClaim(customInput.value);
            });

            customInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    evaluateCustomClaim(customInput.value);
                }
            });
        }

        // Setup Ticker item clicks
        document.querySelectorAll('.ticker-item').forEach(item => {
            item.addEventListener('click', () => {
                const claimText = item.getAttribute('data-claim');
                if (claimText) {
                    if (customInput) customInput.value = claimText;
                    evaluateCustomClaim(claimText);
                    const meterSection = document.getElementById('meter');
                    if (meterSection) {
                        meterSection.scrollIntoView({ behavior: 'smooth' });
                    }
                }
            });
        });

        // Setup Counters
        initCounters();

        // Setup Easter Egg
        initEasterEgg();

        // Audio activation on first click anywhere
        document.body.addEventListener('click', () => {
            initAudio();
        }, { once: true });
    });

})();
