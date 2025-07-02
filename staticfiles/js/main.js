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
                    <article>
                        <div class="bg-white border border-red-500 rounded-xl shadow-md hover:shadow-lg hover:-translate-y-1 transition-all h-full">
                            <img src="${course.image}" alt="${course.course_name}" class="card-img-top rounded-t-xl" loading="lazy" />
                            <div class="p-4">
                                <h5 class="font-bold text-base mb-2">${course.course_name}</h5>
                                <div class="flex items-center mb-2">
                                    <img src="${course.org_logo}" alt="Logo ${course.org_kode}" class="rounded-full w-8 h-8" />
                                    <div class="ml-2">
                                        <p class="text-xs mb-0">
                                            <a href="${universityUrl}" class="text-gray-900 font-semibold no-underline">${course.org_kode}</a>
                                        </p>
                                        <p class="text-gray-500 text-xs">${course.instructor_name}</p>
                                    </div>
                                </div>
                                <div class="flex items-center mb-3">
                                    ${stars}
                                    <small class="text-gray-500 ml-1 text-xs">(${course.avg_rating.toFixed(1)}) (${course.num_ratings} reviews)</small>
                                </div>
                                <div class="mb-3">
                                    <small class="text-gray-500 text-xs">Enrolled: ${course.num_enrollments}</small>
                                </div>
                                <a href="${courseUrl}" class="block w-full text-center bg-white border border-red-500 text-red-500 px-4 py-2 rounded hover:bg-red-500 hover:text-white no-underline text-xs min-h-[44px] flex items-center justify-center">Detail</a>
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