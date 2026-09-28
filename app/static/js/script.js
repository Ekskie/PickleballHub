function switchTab(tabId) {
    const oldForm = document.querySelector('.auth-form.active');
    const newForm = document.getElementById('form-' + tabId);
    
    if (!oldForm || oldForm === newForm) return;

    // Update buttons
    document.getElementById('btn-login').classList.remove('active');
    document.getElementById('btn-signup').classList.remove('active');
    document.getElementById('btn-' + tabId).classList.add('active');

    const wrapper = document.getElementById('forms-wrapper');
    
    // Fix current height
    wrapper.style.height = oldForm.offsetHeight + 'px';
    
    // Crossfade old UI out
    oldForm.style.opacity = '0';
    oldForm.style.transform = 'translateY(-10px)';
    oldForm.style.transition = 'all 0.2s ease';
    
    setTimeout(() => {
        // Strip out old state
        oldForm.classList.remove('active');
        oldForm.style.opacity = '';
        oldForm.style.transform = '';
        oldForm.style.transition = '';
        
        // Prep new form measurement securely
        newForm.style.visibility = 'hidden';
        newForm.style.display = 'flex';
        newForm.style.position = 'absolute';
        
        const targetHeight = newForm.offsetHeight;
        
        // Strip inline hacks, prep for class-based layout
        newForm.style.visibility = '';
        newForm.style.display = '';
        newForm.style.position = '';
        
        // Add active to trigger the CSS keyframes gracefully
        newForm.classList.add('active');
        
        // Stretch or shrink the wrapper
        wrapper.style.height = targetHeight + 'px';
        
        // Release lock
        setTimeout(() => {
            wrapper.style.height = 'auto';
        }, 400); // Match CSS timer constraints
    }, 200); // Give previous form 200ms to visually leave
}

function getSelectedRole() {
    const selectedInput = document.getElementById('selected-role');
    return selectedInput ? (selectedInput.value || 'player') : 'player';
}

function updateStepperUI(visualStep) {
    const role = getSelectedRole();
    const isOwner = (role === 'owner');

    // Badge text
    const badgeText = document.getElementById('step-badge-text');
    if (badgeText) {
        const stepLabelsOwner = {
            1: "Step 1 of 5 · Role Selection",
            2: "Step 2 of 5 · Owner Information",
            3: "Step 3 of 5 · First Facility Details",
            4: "Step 4 of 5 · KYC Verification Documents",
            5: "Step 5 of 5 · Account Credentials"
        };
        const stepLabelsGeneral = {
            1: "Step 1 of 3 · Role Selection",
            2: "Step 2 of 3 · Personal Profile",
            3: "Step 3 of 3 · Account Credentials"
        };
        badgeText.textContent = isOwner ? (stepLabelsOwner[visualStep] || `Step ${visualStep} of 5`) : (stepLabelsGeneral[visualStep] || `Step ${visualStep} of 3`);
    }

    // Stepper dots
    const stepperContainer = document.getElementById('signup-stepper');
    if (stepperContainer) {
        const indicators = stepperContainer.querySelectorAll('.step-indicator');
        indicators.forEach((ind, index) => {
            const stepNum = index + 1;
            ind.classList.remove('active', 'completed');
            if (stepNum < visualStep) {
                ind.classList.add('completed');
            } else if (stepNum === visualStep) {
                ind.classList.add('active');
            }
        });
    }

    // Submit button label
    const submitBtn = document.getElementById('signup-submit-btn');
    if (submitBtn) {
        if (isOwner) {
            submitBtn.innerHTML = 'Create Account & Submit Facility <i class="ph ph-check"></i>';
        } else {
            submitBtn.innerHTML = 'Create Account <i class="ph ph-check"></i>';
        }
    }
}

function setOwnerFieldsRequired(isRequired) {
    const facName = document.getElementById('reg-facility-name');
    const facLoc = document.getElementById('reg-facility-location');
    const tctInput = document.getElementById('kyc_tct_input');
    const permitInput = document.getElementById('kyc_permit_input');

    if (facName) facName.required = isRequired;
    if (facLoc) facLoc.required = isRequired;
    if (tctInput) tctInput.required = isRequired;
    if (permitInput) permitInput.required = isRequired;
}

function selectRoleGrid(role) {
    // Hidden Input value update
    const selectedInput = document.getElementById('selected-role');
    if (selectedInput) selectedInput.value = role;

    // Toggle active classes on cards
    document.querySelectorAll('.role-choice-card').forEach(card => {
        card.classList.remove('active');
    });
    
    const clickedCard = document.getElementById('role-card-' + role);
    if (clickedCard) clickedCard.classList.add('active');

    // Proficiency Group Logic
    const profGroup = document.getElementById('proficiency-group');
    const profInput = document.getElementById('proficiency-input');
    
    if (profGroup && profInput) {
        if (role === 'player') {
            profGroup.classList.remove('hidden-group');
            profInput.setAttribute('required', 'true');
        } else {
            profGroup.classList.add('hidden-group');
            profInput.removeAttribute('required');
        }
    }

    // Dynamic Stepper dots
    const stepperContainer = document.getElementById('signup-stepper');
    if (stepperContainer) {
        if (role === 'owner') {
            stepperContainer.innerHTML = `
                <div class="step-indicator active small" id="step-ind-1" title="Role">1</div>
                <div class="step-indicator small" id="step-ind-2" title="Owner Profile">2</div>
                <div class="step-indicator small" id="step-ind-3" title="Facility Venue">3</div>
                <div class="step-indicator small" id="step-ind-4" title="KYC Verification">4</div>
                <div class="step-indicator small" id="step-ind-5" title="Account Credentials">5</div>
            `;
            setOwnerFieldsRequired(true);
        } else {
            stepperContainer.innerHTML = `
                <div class="step-indicator active" id="step-ind-1" title="Role">1</div>
                <div class="step-indicator" id="step-ind-2" title="Personal Details">2</div>
                <div class="step-indicator" id="step-ind-3" title="Account Credentials">3</div>
            `;
            setOwnerFieldsRequired(false);
        }
    }

    updateStepperUI(1);
}

function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const icon = input.nextElementSibling;
    
    if (input.type === 'password') {
        input.type = 'text';
        if (icon) {
            icon.classList.remove('ph-eye');
            icon.classList.add('ph-eye-slash');
        }
    } else {
        input.type = 'password';
        if (icon) {
            icon.classList.remove('ph-eye-slash');
            icon.classList.add('ph-eye');
        }
    }
}

function handleKycFileSelect(input, type) {
    const zone = document.getElementById('zone-kyc-' + type);
    const label = document.getElementById('label-kyc-' + type);
    const badge = document.getElementById('badge-kyc-' + type);
    const icon = document.getElementById('icon-kyc-' + type);

    if (input.files && input.files[0]) {
        const file = input.files[0];
        const sizeMb = (file.size / (1024 * 1024)).toFixed(1);

        if (file.size > 10 * 1024 * 1024) {
            alert(`File "${file.name}" exceeds the 10 MB limit (${sizeMb} MB). Please choose a smaller file.`);
            input.value = '';
            if (zone) zone.classList.remove('has-file');
            if (badge) badge.style.display = 'none';
            return;
        }

        if (zone) {
            zone.classList.add('has-file');
            zone.style.borderColor = '#22c55e';
        }
        if (icon) icon.className = 'ph ph-check-circle upload-icon';
        if (label) label.textContent = file.name;
        if (badge) {
            badge.style.display = 'inline-flex';
            badge.innerHTML = `<i class="ph ph-file-check"></i> ${sizeMb} MB • Ready`;
        }
    } else {
        if (zone) {
            zone.classList.remove('has-file');
            zone.style.borderColor = '';
        }
        if (badge) badge.style.display = 'none';
    }
}

function handleFacilityPhotoSelect(input) {
    const label = document.getElementById('label-fac-img');
    const badge = document.getElementById('badge-fac-img');
    const zone = document.getElementById('zone-fac-img');
    if (input.files && input.files[0]) {
        const file = input.files[0];
        const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
        if (zone) zone.classList.add('has-file');
        if (label) label.textContent = file.name;
        if (badge) {
            badge.style.display = 'inline-flex';
            badge.innerHTML = `<i class="ph ph-image"></i> ${sizeMb} MB`;
        }
    }
}

function nextSignupStep(currentStep) {
    const role = getSelectedRole();
    const isOwner = (role === 'owner');

    const currentStepEl = document.getElementById('signup-step-' + currentStep);
    if (!currentStepEl) return;

    // Validate inputs in current step
    const inputs = currentStepEl.querySelectorAll('input, select, textarea');
    for (let i = 0; i < inputs.length; i++) {
        if (inputs[i].offsetParent === null) continue;
        
        if (!inputs[i].checkValidity()) {
            inputs[i].reportValidity();
            return;
        }
    }

    // Dedicated KYC validation on Step 4 for owner
    if (isOwner && currentStep === 4) {
        const tctInput = document.getElementById('kyc_tct_input');
        const permitInput = document.getElementById('kyc_permit_input');

        if (!tctInput || !tctInput.files || tctInput.files.length === 0) {
            const tctZone = document.getElementById('zone-kyc-tct');
            if (tctZone) {
                tctZone.style.borderColor = '#ef4444';
                tctZone.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            alert('Please upload your Transfer Certificate of Title (TCT) / Original Certificate of Title (OCT) document.');
            return;
        }

        if (!permitInput || !permitInput.files || permitInput.files.length === 0) {
            const permitZone = document.getElementById('zone-kyc-permit');
            if (permitZone) {
                permitZone.style.borderColor = '#ef4444';
                permitZone.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            alert('Please upload your Business Permit document.');
            return;
        }
    }

    // Determine target next step
    let nextStep = currentStep + 1;
    if (!isOwner && currentStep === 2) {
        // Player & Clubadmin jump straight to Step 5 (Credentials)
        nextStep = 5;
    }

    currentStepEl.classList.remove('active');
    const nextStepEl = document.getElementById('signup-step-' + nextStep);
    if (nextStepEl) {
        nextStepEl.classList.add('active');
    }

    const visualStep = (!isOwner && nextStep === 5) ? 3 : nextStep;
    updateStepperUI(visualStep);
}

function prevSignupStep(currentStep) {
    const role = getSelectedRole();
    const isOwner = (role === 'owner');

    const currentStepEl = document.getElementById('signup-step-' + currentStep);
    if (!currentStepEl) return;

    let prevStep = currentStep - 1;
    if (!isOwner && currentStep === 5) {
        // Non-owners return from Step 5 to Step 2
        prevStep = 2;
    }

    currentStepEl.classList.remove('active');
    const prevStepEl = document.getElementById('signup-step-' + prevStep);
    if (prevStepEl) {
        prevStepEl.classList.add('active');
    }

    const visualStep = (!isOwner && prevStep === 5) ? 3 : prevStep;
    updateStepperUI(visualStep);
}

function validateFinalStep() {
    const stepEl = document.getElementById('signup-step-5');
    if (!stepEl) return false;
    const inputs = stepEl.querySelectorAll('input, select');
    for (let i = 0; i < inputs.length; i++) {
        if (!inputs[i].checkValidity()) {
            inputs[i].reportValidity();
            return false;
        }
    }
    return true;
}

/* Redesign Theme Toggling */
function toggleTheme() {
    const html = document.documentElement;
    const isDark = !html.classList.contains('dark-mode');
    if (isDark) {
        html.classList.add('dark-mode');
        html.setAttribute('data-theme', 'dark');
        if (document.body) {
            document.body.classList.add('dark-mode');
            document.body.setAttribute('data-theme', 'dark');
        }
        localStorage.setItem('theme', 'dark');
    } else {
        html.classList.remove('dark-mode');
        html.setAttribute('data-theme', 'light');
        if (document.body) {
            document.body.classList.remove('dark-mode');
            document.body.setAttribute('data-theme', 'light');
        }
        localStorage.setItem('theme', 'light');
    }

    const icons = document.querySelectorAll('#theme-icon, #themeToggleIcon, .theme-icon');
    icons.forEach(icon => {
        if (isDark) {
            icon.classList.remove('ph-moon');
            icon.classList.add('ph-sun');
        } else {
            icon.classList.remove('ph-sun');
            icon.classList.add('ph-moon');
        }
    });
}

/* Editorial Hero Slider */
let currentSlide = 0;
let sliderInterval;

function showSlide(index) {
    const slides = document.querySelectorAll('.editorial-slide');
    const dots = document.querySelectorAll('.slider-dot');
    if (slides.length === 0) return;
    
    if (index >= slides.length) currentSlide = 0;
    else if (index < 0) currentSlide = slides.length - 1;
    else currentSlide = index;

    slides.forEach((slide, i) => {
        slide.classList.toggle('active', i === currentSlide);
    });
    dots.forEach((dot, i) => {
        dot.classList.toggle('active', i === currentSlide);
    });
}

function nextSlide() {
    showSlide(currentSlide + 1);
}

function prevSlide() {
    showSlide(currentSlide - 1);
}

function setSlide(index) {
    showSlide(index);
    resetSliderTimer();
}

function startSliderTimer() {
    sliderInterval = setInterval(nextSlide, 6000); // Rotate every 6s
}

function resetSliderTimer() {
    clearInterval(sliderInterval);
    startSliderTimer();
}

/* Page Initialization */
document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Hero Slider if present
    const slides = document.querySelectorAll('.editorial-slide');
    if (slides.length > 0) {
        showSlide(0);
        startSliderTimer();
    }

    // 2. Pre-select Signup Role from URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const roleParam = urlParams.get('role');
    if (roleParam && (roleParam === 'player' || roleParam === 'clubadmin' || roleParam === 'owner')) {
        selectRoleGrid(roleParam);
    }

    // 3. Initialize Scroll to Top Button
    (function() {
        if (document.getElementById('scrollToTopBtn')) return;
        const btn = document.createElement('button');
        btn.id = 'scrollToTopBtn';
        btn.className = 'scroll-to-top-btn';
        btn.setAttribute('aria-label', 'Scroll to top');
        btn.innerHTML = '<i class="ph ph-arrow-up"></i>';
        document.body.appendChild(btn);

        btn.addEventListener('click', () => {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });

        window.addEventListener('scroll', () => {
            if (window.scrollY > 300) {
                btn.classList.add('visible');
            } else {
                btn.classList.remove('visible');
            }
        });
    })();
});
