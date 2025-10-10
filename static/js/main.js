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
//popular courses
document.addEventListener('DOMContentLoaded', function () {
  const coursesList = document.getElementById('courses-list');
  if (!coursesList) return;

  fetch('/popular_courses/')
    .then(response => response.json())
    .then(data => {
      coursesList.innerHTML = ''; // clear existing content

      data.courses.forEach(course => {
        const courseUrl = `/course-detail/${course.id}/${encodeURIComponent(course.slug)}/`;
        const instructorPhoto = course.instructor_photo || '/static/images/user-default.webp';
        const org_logo = course.org_logo || '/static/images/user-default.webp';

        const isFree = (course.user_payment === 0);

        // Use rating stars from backend directly
        const ratingStars = [
          ...Array(course.full_stars).fill(`<svg class="h-4 w-4 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
            <path d="M10 15l-5.878 3.09L5.49 12.18 1 7.91l6.061-.545L10 2.5l2.939 4.865 6.061.545-4.49 4.27 1.368 5.91z"/>
          </svg>`),
          course.half_star ? `<svg class="h-4 w-4 text-yellow-400" viewBox="0 0 20 20">
            <defs>
              <linearGradient id="half-${course.id}">
                <stop offset="50%" stop-color="currentColor"/>
                <stop offset="50%" stop-color="transparent"/>
              </linearGradient>
            </defs>
            <path fill="url(#half-${course.id})" d="M10 15l-5.878 3.09L5.49 12.18 1 7.91l6.061-.545L10 2.5l2.939 4.865 6.061.545-4.49 4.27 1.368 5.91z"/>
          </svg>` : '',
          ...Array(course.empty_stars).fill(`<svg class="h-4 w-4 text-gray-300" fill="currentColor" viewBox="0 0 20 20">
            <path d="M10 15l-5.878 3.09L5.49 12.18 1 7.91l6.061-.545L10 2.5l2.939 4.865 6.061.545-4.49 4.27 1.368 5.91z"/>
          </svg>`)
        ].join('');

        const courseHtml = `
                <article 
                        class="course-fade bg-white rounded-xl shadow-md hover:shadow-lg transition p-4 sm:p-5 flex flex-col h-full"
                        itemscope 
                        itemtype="https://schema.org/Course"
                      >
                        <a 
                          href="${courseUrl}" 
                          title="View course: ${course.course_name}" 
                          class="block no-underline flex-grow flex flex-col"
                          itemprop="url"
                        >

                          <!-- Thumbnail -->
                          <div class="relative rounded-md overflow-hidden mb-4">
                            <img 
                              src="${course.image || '/static/images/placeholder-300.webp'}"
                              srcset="
                                ${course.image || '/static/images/placeholder-150.webp'} 150w,
                                ${course.image || '/static/images/placeholder-300.webp'} 300w,
                                ${course.image || '/static/images/placeholder-600.webp'} 600w"
                              sizes="(max-width: 640px) 100vw, 300px"
                              alt="${course.course_name || 'Course Image'}"
                              class="w-full aspect-[4/3] object-cover transition-transform duration-300 hover:scale-105 rounded-md"
                              loading="lazy"
                              decoding="async"
                              itemprop="image"
                            >
                            ${isFree ? `<span class="absolute top-2 left-2 bg-green-600 text-white text-xs font-semibold px-2 py-1 rounded shadow">FREE</span>` : ''}
                          </div>

                          <!-- Title -->
                          <h2 
                            class="text-base font-semibold text-gray-900 line-clamp-2 mb-2 hover:text-green-700 transition-colors duration-200"
                            itemprop="name"
                          >
                            ${course.course_name || 'Untitled Course'}
                          </h2>

                          <!-- Pricing -->
                          ${!isFree ? `
                            <div class="flex flex-wrap items-center gap-2 mb-3">
                              <span class="text-green-700 font-semibold text-base whitespace-nowrap">
                                IDR ${typeof course.user_payment === 'number' ? course.user_payment.toLocaleString() : 'N/A'}
                              </span>
                            </div>
                          ` : ''}

                          <!-- Rating & Enrollments -->
                          <div class="flex flex-wrap items-center justify-between text-sm mb-4 gap-2">
                            <!-- Rating -->
                            <div class="flex items-center ${course.num_ratings === 0 ? 'text-gray-300' : 'text-yellow-400'}">
                              ${ratingStars}
                              <span class="ml-2 text-gray-600 text-xs">(${course.num_ratings || 0})</span>
                            </div>

                            <!-- Enrollments -->
                            <div class="flex items-center text-gray-500 text-xs space-x-1">
                              <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                                <path d="M20 21v-2a4 4 0 0 0-3-3.87" />
                                <path d="M4 21v-2a4 4 0 0 1 3-3.87" />
                                <circle cx="12" cy="7" r="4" />
                              </svg>
                              <span>${course.num_enrollments || 0}</span>
                            </div>
                          </div>

                          <!-- Language -->
                          <p class="flex items-center text-xs text-gray-500 mb-4 space-x-1 truncate">
                            <svg class="h-4 w-4 flex-shrink-0 text-gray-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                              <circle cx="12" cy="12" r="10" />
                              <line x1="2" y1="12" x2="22" y2="12" />
                              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                            </svg>
                            <span>&nbsp; ${course.language ? course.language.charAt(0).toUpperCase() + course.language.slice(1) : 'N/A'}</span>
                          </p>

                          <!-- Footer: Instructor & Partner -->
                          <div class="flex items-center mt-auto pt-3 border-t border-gray-200">
                            <img 
                              src="${org_logo}" 
                              alt="${course.org_name || 'Partner'}" 
                              class="w-6 h-6 rounded-full mr-3 object-cover border border-gray-200"
                              itemprop="provider logo"
                            >
                            <div class="flex flex-col text-xs leading-tight truncate">
                              <p class="text-gray-700 font-semibold truncate" itemprop="provider" itemscope itemtype="https://schema.org/Organization">
                                <span itemprop="name">${course.org_name || 'Unknown Partner'}</span>
                              </p>
                              <p class="text-gray-600 truncate">${course.instructor_name || 'N/A'}</p>
                            </div>
                          </div>

                        </a>
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


 






  