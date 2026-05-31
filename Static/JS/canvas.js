const canvas = document.getElementById('canvas-bg');
const ctx = canvas.getContext('2d');
let width, height;

function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
}
window.addEventListener('resize', resize);
resize();

const words = ["FAKE", "REAL", "HOAX", "SCAM", "TRUTH", "RUMOUR", "CLICKBAIT", "PROPAGANDA", "DEBUNKIT", "EVIDENCE", "ANOMALY", "VERIFIED", "SYNTHETIC", "DEEPFAKE", "FABRICATION", "SOURCE", "NDTV", "TIMES", "REUTERS", "BUSTED", "LEGIT", "MISLEADING", "CONSPIRACY", "ALLEGED", "SUPPRESSED", "EXPOSED", "AMAN", "JOSHI", "SOULNINJA", "MURDER", "VIRUS", "CURE", "CLIMATE", "CHANGE", "ELECTION", "FRAUD", "CELEBRITY", "DEATH", "BIRTH", "MARRIAGE", "DIVORCE", "BANKRUPTCY", "ARREST", "SCANDAL"];
let drops = [];

class NewsDrop {
    constructor() {
        this.reset(true);
    }
    reset(randomY = false) {
        this.text = words[Math.floor(Math.random() * words.length)];
        ctx.font = '14px Courier New';
        this.width = ctx.measureText(this.text).width;
        this.height = 14;
        this.x = Math.random() * (width - this.width);
        this.y = randomY ? Math.random() * height : -50;

        // SPEED TWEAK: Increased base speed and multiplier for a slightly faster fall
        this.speed = Math.random() * 2.0 + 1.0;

        // COLOR TWEAK: Probability-based color assignment using your UI palette
        const colorRoll = Math.random();
        if (colorRoll > 0.95) {
            this.color = 'rgba(232, 200, 74, 0.4)';  // Gold Accent (5% chance)
        } else if (colorRoll > 0.85) {
            this.color = 'rgba(224, 82, 82, 0.25)'; // Danger Red (10% chance)
        } else if (colorRoll > 0.75) {
            this.color = 'rgba(62, 207, 122, 0.25)'; // Success Green (10% chance)
        } else if (colorRoll > 0.50) {
            this.color = 'rgba(212, 218, 232, 0.15)'; // Ghost White (25% chance)
        } else {
            this.color = 'rgba(74, 81, 104, 0.3)';   // Muted Blue/Gray (Default 50%)
        }
    }
    update() {
        this.y += this.speed;
        if (this.y > height + 50) this.reset();
    }
    draw() {
        ctx.fillStyle = this.color;
        ctx.font = '14px Courier New';
        ctx.fillText(this.text, this.x, this.y);
    }
}

function init() {
    drops = [];
    let numberOfDrops = Math.floor((width * height) / 8000);
    for (let i = 0; i < numberOfDrops; i++) { drops.push(new NewsDrop()); }
}

function animate() {
    // This creates the fading "trail" effect behind the words
    ctx.fillStyle = 'rgba(13, 15, 20, 0.2)';
    ctx.fillRect(0, 0, width, height);

    for (let i = 0; i < drops.length; i++) {
        drops[i].update();
        drops[i].draw();
    }
    requestAnimationFrame(animate);
}

canvas.addEventListener('click', (e) => {
    const mouseX = e.clientX;
    const mouseY = e.clientY;

    for (let i = 0; i < drops.length; i++) {
        let drop = drops[i];
        if (mouseX >= drop.x &&
            mouseX <= drop.x + drop.width &&
            mouseY >= drop.y - drop.height &&
            mouseY <= drop.y) {

            console.log(`[!] Easter Egg Triggered on: ${drop.text}`);

            // The Payload: Open a search for the word they successfully sniped
            window.open(`https://duckduckgo.com/?q=define+${drop.text.toLowerCase()}`, '_blank');

            break;
        }
    }
});

init();
animate();