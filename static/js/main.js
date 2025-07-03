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
                                <article class="group relative bg-white rounded-2xl shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-300 overflow-hidden">
                                    <!-- Diagonal Cut Background -->
                                    <div class="absolute top-0 left-0 w-full h-1/2 bg-[linear-gradient(45deg,#000000_0%,#333333_100%)] opacity-10 transform -skew-y-6"></div>
                                    
                                    <!-- Course Thumbnail -->
                                    <div class="relative z-10">
                                    <img src="${course.image || 'https://via.placeholder.com/300x150'}" alt="Thumbnail for ${course.course_name}" class="w-full h-48 object-cover rounded-t-2xl" loading="lazy" width="300" height="150">
                                    </div>

                                    <!-- Card Content -->
                                    <div class="relative z-10 p-6">
                                    <!-- Course Title -->
                                    <h5 class="font-semibold text-lg text-black group-hover:text-red-500 transition-colors mb-3">
                                        <a href="${courseUrl}" class="no-underline text-black group-hover:text-red-500 focus:text-red-500">${course.course_name}</a>
                                    </h5>

                                    <!-- Organization and Instructor -->
                                    <div class="flex items-center mb-4">
                                        <img src="${course.org_logo || 'https://via.placeholder.com/40x40'}" alt="Logo of ${course.org_kode}" class="w-10 h-10 rounded-full" loading="lazy" width="40" height="40">
                                        <div class="ml-3">
                                        <p class="text-sm font-medium text-black hover:text-red-500 transition-colors mb-1">
                                            <a href="${universityUrl}" class="no-underline text-black hover:text-red-500 focus:text-red-500">${course.org_kode}</a>
                                        </p>
                                        <p class="text-sm text-gray-600 hover:text-red-500 transition-colors">${course.instructor_name}</p>
                                        </div>
                                    </div>

                                    <!-- Rating and Enrollment -->
                                    <div class="flex items-center mb-4">
                                        <div class="flex">
                                        ${stars} <!-- Assuming stars is a string of star icons (e.g., <i class="fas fa-star text-yellow-500"></i>) -->
                                        </div>
                                        <span class="text-sm text-gray-600 ml-2 hover:text-red-500 transition-colors">(${course.avg_rating.toFixed(1)}) (${course.num_ratings} reviews)</span>
                                    </div>
                                    <p class="text-sm text-gray-600 mb-4 hover:text-red-500 transition-colors">Enrolled: ${course.num_enrollments}</p>

                                    <!-- Action Buttons -->
                                    <div class="flex justify-between gap-4">
                                        <a href="${courseUrl}" class="flex-1 text-center bg-black text-white px-4 py-2 rounded-lg hover:bg-gray-800 hover:text-red-500 focus:outline focus:outline-2 focus:outline-red-500 transition-colors text-sm font-medium">View Details</a>
                                        <button class="flex-1 text-center bg-gray-200 text-black px-4 py-2 rounded-lg hover:bg-gray-300 hover:text-red-500 focus:outline focus:outline-2 focus:outline-red-500 transition-colors text-sm font-medium">Add to Cart</button>
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