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
                            <article class="group relative bg-white rounded-xl shadow-md hover:shadow-lg transition-colors duration-300 overflow-hidden">
                                <!-- Course Thumbnail -->
                                <div class="relative w-full h-32 sm:h-40 bg-gray-200">
                                <img 
                                    src="${course.image || '/static/images/placeholder-300.webp'}" 
                                    srcset="${course.image || '/static/images/placeholder-150.webp'} 150w, ${course.image || '/static/images/placeholder-300.webp'} 300w" 
                                    sizes="(max-width: 600px) 150px, 300px" 
                                    alt="Thumbnail for ${course.course_name}" 
                                    class="w-full h-full object-contain rounded-t-xl" 
                                    loading="lazy" 
                                    width="300" 
                                    height="150">
                                </div>

                                <!-- Card Content -->
                                <div class="p-4 sm:p-6">
                                <!-- Course Title -->
                                <h5 class="font-semibold text-sm sm:text-base text-black group-hover:text-red-500 transition-colors mb-3">
                                    <a href="${courseUrl}" class="no-underline text-black group-hover:text-red-500 focus:text-red-500">${course.course_name}</a>
                                </h5>

                                <!-- Organization and Instructor -->
                                <div class="flex items-center mb-3">
                                    <img 
                                    src="${course.org_logo || '/static/images/org-logo-40.webp'}" 
                                    srcset="${course.org_logo || '/static/images/org-logo-20.webp'} 20w, ${course.org_logo || '/static/images/org-logo-40.webp'} 40w" 
                                    sizes="(max-width: 600px) 20px, 40px" 
                                    alt="Logo of ${course.org_kode}" 
                                    class="w-8 h-8 sm:w-10 sm:h-10 rounded-full" 
                                    loading="lazy" 
                                    width="40" 
                                    height="40">
                                    <div class="ml-2 sm:ml-3">
                                    <p class="text-xs sm:text-sm font-medium text-black hover:text-red-500 transition-colors mb-1">
                                        <a href="${universityUrl}" class="no-underline text-black hover:text-red-500 focus:text-red-500">${course.org_kode}</a>
                                    </p>
                                    <p class="text-xs sm:text-sm text-gray-600 hover:text-red-500 transition-colors">${course.instructor_name}</p>
                                    </div>
                                </div>

                                <!-- Rating and Enrollment -->
                                <div class="flex items-center mb-3">
                                    <div class="flex">
                                    ${Array(5).fill().map(() => '<svg class="w-3 h-3 sm:w-4 sm:h-4 text-yellow-500" viewBox="0 0 24 24" fill="currentColor"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/></svg>').join('')}
                                    </div>
                                    <span class="text-xs sm:text-sm text-gray-600 ml-2 hover:text-red-500 transition-colors">(${course.avg_rating.toFixed(1)}) (${course.num_ratings} reviews)</span>
                                </div>
                                <div class="flex items-center mb-4">
                                    <svg class="w-3 h-3 sm:w-4 sm:h-4 text-gray-600 group-hover:text-red-500 mr-1" viewBox="0 0 24 24" fill="currentColor">
                                    <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                                    </svg>
                                    <span class="text-xs sm:text-sm text-gray-600 group-hover:text-red-500 transition-colors">${course.num_enrollments}</span>
                                </div>

                                <!-- Action Buttons -->
                                <div class="flex justify-between gap-3">
                                    <a href="${courseUrl}" class="flex-1 text-center bg-black text-white px-3 sm:px-4 py-2 rounded-lg hover:bg-gray-800 hover:text-red-500 focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-colors text-xs sm:text-sm font-medium">View Details</a>
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