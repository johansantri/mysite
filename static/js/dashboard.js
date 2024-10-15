
$( '#partner_email' ).select2( {
  theme: 'bootstrap-5'
} );

$( '#author' ).select2( {
  theme: 'bootstrap-5'
} );

function slugify(text) {
	return text
	  .toString() // Cast to string
	  .toLowerCase() // Convert the string to lowercase letters
	  .normalize('NFD') // The normalize() method returns the Unicode Normalization Form of a given string.
	  .trim() // Remove whitespace from both sides of a string
	  .replace(/\s+/g, '-') // Replace spaces with -
	  .replace(/[^\w\-]+/g, '') // Remove all non-word chars
	  .replace(/\-\-+/g, '-'); // Replace multiple - with single -
  }
  
  function listingslug(text) {
	document.getElementById("slug").value = slugify(text);
  }

 