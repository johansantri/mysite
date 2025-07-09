//untuk menu static
const toggleBtn = document.getElementById('navbarToggle');
        const closeBtn = document.getElementById('closeMenu');
        const mobileMenu = document.getElementById('navbarNavMobile');
        const overlay = document.getElementById('overlay');

        toggleBtn.addEventListener('click', () => {
            mobileMenu.classList.add('active');
            overlay.classList.add('active');
        });

        closeBtn.addEventListener('click', () => {
            mobileMenu.classList.remove('active');
            overlay.classList.remove('active');
        });

        overlay.addEventListener('click', () => {
            mobileMenu.classList.remove('active');
            overlay.classList.remove('active');
        });

//popular course
document.addEventListener('DOMContentLoaded', function() {
    const coursesList = document.getElementById('courses-list');
    if (!coursesList) return;

    fetch('/popular_courses/')
        .then(response => response.json())
        .then(data => {
            coursesList.innerHTML = '';  // kosongkan dulu

            data.courses.forEach(course => {
                let stars = '';
                for (let i = 0; i < course.full_stars; i++) {
                    stars += '<i class="fas fa-star text-yellow-500 text-xs"></i>';
                }
                if (course.half_star) {
                    stars += '<i class="fas fa-star-half-alt text-yellow-500 text-xs"></i>';
                }
                for (let i = 0; i < course.empty_stars; i++) {
                    stars += '<i class="far fa-star text-yellow-500 text-xs"></i>';
                }

                const courseUrl = `/course-detail/${course.id}/${course.slug}/`;
                const universityUrl = `/org-partner/${course.org_slug}/`;
                const instructorPhoto = course.instructor_photo || '/static/images/default-avatar.png';

                const courseHtml = `
                    <article class="group relative bg-white rounded-xl shadow hover:shadow-md transition-all duration-300 overflow-hidden ring-1 ring-gray-100">

                    <!-- Thumbnail -->
                    <div class="relative w-full aspect-[3/2] bg-gray-100 overflow-hidden rounded-t-xl">
                        <img
                        src="${course.image || '/static/images/placeholder-300.webp'}"
                        srcset="
                            ${course.image || '/static/images/placeholder-150.webp'} 150w,
                            ${course.image || '/static/images/placeholder-300.webp'} 300w,
                            ${course.image || '/static/images/placeholder-600.webp'} 600w"
                        sizes="(max-width: 640px) 100vw, 300px"
                        alt="Thumbnail for ${course.course_name}"
                        class="absolute inset-0 w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
                        loading="lazy"
                        decoding="async"
                        >
                    </div>

                    <!-- Content -->
                    <div class="p-4 sm:p-5 space-y-3">

                        <!-- Title -->
                        <h3 class="text-base sm:text-lg font-semibold text-gray-900 group-hover:text-red-600 line-clamp-2">
                        <a href="${courseUrl}" class="focus:outline-none focus:text-red-600">
                            ${course.course_name}
                        </a>
                        </h3>

                        <!-- Org + Instructor -->
                        <div class="flex items-center gap-3">
                        <img
                            src="${course.org_logo || '/static/images/org-logo-40.webp'}"
                            srcset="
                            ${course.org_logo || '/static/images/org-logo-20.webp'} 20w,
                            ${course.org_logo || '/static/images/org-logo-40.webp'} 40w"
                            sizes="(max-width: 640px) 32px, 40px"
                            alt="Logo of ${course.org_kode}"
                            class="w-8 h-8 rounded-full object-cover"
                            loading="lazy"
                            decoding="async"
                        >
                        <div class="text-sm leading-tight">
                            <a href="${universityUrl}" class="text-gray-800 font-medium hover:text-red-600">${course.org_kode}</a>
                            <div class="text-gray-500">${course.instructor_name}</div>
                        </div>
                        </div>

                        <!-- Rating -->
                        <div class="flex items-center gap-1 text-sm">
                        <svg class="w-4 h-4 text-yellow-500" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/>
                        </svg>
                        <span class="font-medium text-gray-800">${course.avg_rating ? course.avg_rating.toFixed(1) : '0.0'}</span>
                        <span class="text-gray-500">(${course.num_ratings || 0})</span>
                        </div>

                        <!-- Enrollment -->
                        <div class="flex items-center text-sm text-gray-600 group-hover:text-red-600">
                        <svg class="w-4 h-4 mr-1 text-gray-500 group-hover:text-red-600" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5s-3 1.34-3 3 1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5C15 14.17 10.33 13 8 13zm8 0c-.29 0-.62.02-.97.05C15.59 13.59 17 14.53 17 16V19h5v-2.5c0-2.33-4.67-3.5-7-3.5z"/>
                        </svg>
                        ${course.num_enrollments || 0}
                        </div>

                        <!-- CTA -->
                        <div>
                        <a href="${courseUrl}"
                            class="block w-full text-center bg-black text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-gray-800 hover:text-red-500 transition-colors focus:outline-none focus:ring-2 focus:ring-red-500">
                            View Details
                        </a>
                        </div>
                    </div>
                    </article>
                    `;




                coursesList.insertAdjacentHTML('beforeend', courseHtml);
            });
        })
        .catch(err => {
            coursesList.innerHTML = '<p class="text-red-600">Failed to load courses. Please try again later.</p>';
            console.error(err);
        });
});


//untuk course detail

 document.addEventListener("DOMContentLoaded", function() {
        if (typeof Fancybox !== 'undefined') {
            Fancybox.bind('[data-fancybox="video-gallery"]', {
                infinite: false,
                arrows: true,
                closeButton: "top",
                dragToClose: true
            });
        } else {
            console.warn('Fancybox is not loaded. Video lightbox functionality will not work.');
        }
    });

    function openShareWindow() {
        const courseUrl = window.location.href;
        const encodedUrl = encodeURIComponent(courseUrl);
        const shareUrls = {
            facebook: `https://www.facebook.com/sharer/sharer.php?u=${encodedUrl}`,
            twitter: `https://twitter.com/intent/tweet?url=${encodedUrl}&text=Check out this course!`,
            whatsapp: `https://api.whatsapp.com/send?text=Check out this course: ${encodedUrl}`
        };
        const platform = 'facebook';
        const windowOptions = `height=400,width=600,top=${(window.innerHeight / 2 - 200)},left=${(window.innerWidth / 2 - 300)}`;
        if (shareUrls[platform]) {
            window.open(shareUrls[platform], '_blank', windowOptions);
        } else {
            console.error('Platform not supported');
        }
    }

    function toggleReplyForm(formId) {
        const form = document.getElementById(formId);
        form.classList.toggle('hidden');
    }


    //script untuk micro detail
        document.addEventListener("DOMContentLoaded", function() {
        if (typeof Fancybox !== 'undefined') {
            Fancybox.bind('[data-fancybox="video-gallery"]', {
                infinite: false,
                arrows: true,
                closeButton: "top",
                dragToClose: true
            });
        } else {
            console.warn('Fancybox is not loaded. Video lightbox functionality will not work.');
        }
    });

    function openShareWindow() {
        var courseUrl = window.location.href;
        var encodedUrl = encodeURIComponent(courseUrl);
        var shareUrls = {
            facebook: 'https://www.facebook.com/sharer/sharer.php?u=' + encodedUrl,
            twitter: 'https://twitter.com/intent/tweet?url=' + encodedUrl + '&text=Check out this microcredential!',
            whatsapp: 'https://api.whatsapp.com/send?text=Check out this microcredential: ' + encodedUrl
        };
        var platform = 'facebook';
        var windowOptions = 'height=400,width=600,top=' + (window.innerHeight / 2 - 200) + ',left=' + (window.innerWidth / 2 - 300);
        if (shareUrls[platform]) {
            window.open(shareUrls[platform], '_blank', windowOptions);
        } else {
            console.error('Platform not supported');
        }
    }


    //script post detail
    function showReplyForm(commentId) {
    // Hide all reply forms
    document.querySelectorAll('.reply-form').forEach(form => form.classList.add('hidden'));
    // Show the target reply form
    const targetForm = document.getElementById(`reply-form-${commentId}`);
    if (targetForm) {
        targetForm.classList.remove('hidden');
    }
    }