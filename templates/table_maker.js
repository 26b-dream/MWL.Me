var dt_table = function (url) {
   // Values to convert status integers to strings
   {% if form.anime_or_manga == 'anime'%}
      const STATUS_ARRAY = ["Not on List", "Watching", "Completed", "On-Hold", "Dropped", "Plan to Watch"];
   {% else %}
      const STATUS_ARRAY = ["Not on List", "Watching", "Completed", "On-Hold", "Dropped", "Plan to Watch"];
   {% endif %}

   // Don't remember exactly where this method of getting a json response came from but it works
   var asyncData;
   function getdata() {
      const getRecs = async () => {
         const data = await fetch(url, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
         });
         const jsondata = await data.json();
         asyncData = jsondata;
         initialiseTable();
      };
      getRecs();
   }
   getdata();


   function initialiseTable() {
      $(document).ready(function () {
         var table = $('#example').DataTable({
            // Each letter has a specific meaning
            // See: https://datatables.net/reference/option/dom
            dom: "QBftip",
            // Button to switch between table and card view 
            // See: https://www.gyrocode.com/articles/jquery-datatables-card-view/
            buttons: ['csv', {
               text: 'Change View',
               action: function (e, dt, node) {
                  $(dt.table().node()).toggleClass('cards');
                  $('.fa', node).toggleClass(['fa-table', 'fa-id-badge']);
                  dt.draw('page');
               },
               className: 'btn-sm',
               attr: { title: 'Change views' }
            }],
            data: asyncData.data,
            columns: [
               {
                  data: '1',
                  searchable: false, // There is nothing possible to search it's a picture
                  // Make a coumn that is an image that links to MyAnimeList
                  render: function (data, type, full, meta) {
                     var anime_id = asyncData.data[meta.row][2];
                     return "<a href=\"https://myanimelist.net/{{form.anime_or_manga.value}}/" + anime_id + "\">" + "<img src=\"https://api-cdn.myanimelist.net/images/{{form.anime_or_manga.value}}/" + data + ".jpg\">" + "</a>";
                  },
               },
               {
                  data: '2',
                  // Make a column that is the name that links to MyAnimeList
                  render: function (data, type) {
                     return "<a href=\"https://myanimelist.net/{{form.anime_or_manga.value}}/" + data + "\">" + asyncData.names[data] + "</a>";
                  },

               },
               {
                  data: '4',
                  // Make a column that shows the user's status for an anime/manga
                  render: function (data, type) {
                     return STATUS_ARRAY[data];
                  },
               },
               {
                  // Straight show the score used to determine how good the recommendation is
                  data: '0',
               },
               {
                  data: '3',
                  // Shows in depth information about how the score was calculated
                  render: function (data, type) {
                     // Put the most influential entries at the top of the list
                     data.sort(function (a, b) {
                        return b[1] - a[1];
                     });
                     
                     var output = "";
                     for (var i = 0; i < data.length; i++) {
                        output += ("<li>" + asyncData.names[data[i][0].toString()] + " (" + data[i][1] + ")</li>");
                     }
                     // Put everything in a div with a littel score bar so the list doesn't stretch the table
                     // 300px is close to the average size for the images, but it looks like image size varies slightly
                     return '<div class="overflow-scroll" style="max-height:300px"><ul>' + output + '</ul></div>'
                  },
                  visible: false,
               },
            ],

            // Script to make cards from the table
            // See: https://www.gyrocode.com/articles/jquery-datatables-card-view/
            'drawCallback': function (settings) {
               var api = this.api();
               var $table = $(api.table().node());

               if ($table.hasClass('cards')) {

                  // Create an array of labels containing all table headers
                  var labels = [];
                  $('thead th', $table).each(function () {
                     labels.push($(this).text());
                  });

                  // Add data-label attribute to each cell
                  $('tbody tr', $table).each(function () {
                     $(this).find('td').each(function (column) {
                        $(this).attr('data-label', labels[column]);
                     });
                  });

                  var max = 0;
                  $('tbody tr', $table).each(function () {
                     max = Math.max($(this).height(), max);
                  }).height(max);

               } else {
                  // Remove data-label attribute from each cell
                  $('tbody td', $table).each(function () {
                     $(this).removeAttr('data-label');
                  });

                  $('tbody tr', $table).each(function () {
                     $(this).height('auto');
                  });
               }

            }
         })


         // Used for changing column visibility
         // See: https://datatables.net/examples/api/show_hide.html
         $('a.toggle-vis').on('click', function (e) {
            e.preventDefault();

            // Get the column API object
            var column = table.column($(this).attr('data-column'));

            // Toggle the visibility
            column.visible(!column.visible());
         });
      })
   }
   ;
}