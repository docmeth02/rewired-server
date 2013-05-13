function getlog() {
        $.getJSON('/rpc.cgi?type=log&offset=' + window.offset)
        .done(function(data) {
            //alert("Called: " + window.offset);
            var html = "";
            var exten = 0
            $.each(data['log'], function(key, item) {
                var row = ''
                var rowclass = ""

               if (item.hasOwnProperty('RESULT')) {
                    var type = ""
                    switch(item['RESULT']) {
                        case 'ok':
                            type = 'label-success';
                            break;
                        case 'complete':
                            type = 'label-success';
                            rowclass = 'class = "success"';
                            break;
                        case 'aborted':
                            type = 'label-important';
                            rowclass = 'class = "error"';
                            break;
                        case 'failed':
                            type = 'label-important';
                            rowclass = 'class = "error"';
                            break;
                        default:
                            type = 'label-info';
                    }
               }
                if (item.hasOwnProperty('EXTENDED')) {
                //alert("EXTENT");
                row += '<tr '+ rowclass + 'onmouseover="$(\'#log' + exten + '\').collapse(\'show\');"\
                onmouseout="$(\'#log' + exten + '\').collapse(\'hide\');" onclick="$(\'#log\
                '+ exten + '\').collapse(\'toggle\');">';
                }
                else {
                    row += '<tr ' + rowclass + '>';
                }
                row += '<td style="max-width=60px;">'+ item['DATE']+'</td>';
                row += '<td>' + item['USER'] + '</td>';
                var colspan = 'colspan="2"';
                if (item.hasOwnProperty('RESULT')) {
                    colspan = '';
                }
                row += '<td ' + colspan + '>' + item['STRING'];

                if (item.hasOwnProperty('EXTENDED')) {
                    row += '<br /><div id="log' + exten + '" class="collapse"><strong>' + item['EXTENDED'] + '</strong></div>';
                    exten += 1;
                }
                row += '</td>';

                if (item.hasOwnProperty('RESULT')) {
                    row += '<td><span class="label '+ type + '">' + item['RESULT'] + '</span></td>';
                }
                else {
                    row += '<td></td>';
                }
                row += '</tr>'
                html += row;

            $('#log > tbody').html(html);

            });
        var html = "";
        var eventcount = data['count'];
        var pages = Math.ceil(eventcount/window.perpage);
        var curpage = 1;
        if (window.offset != 0) {
            curpage = Math.ceil(window.offset/window.perpage) + 1;
        }
        if (curpage > 1) {
            html += '<ul><li><a href="#" onclick="loadpage('+ (curpage - 1) +'); return false;">Prev</a></li>';
        }
        else {
            html += '<ul><li class="disabled"><a href="#">Prev</a></li>';
        }
        for (var n=1;n<=pages;n++) {
            if ((n == curpage)) {
                html += '<li class="active"><a href="#">' + n + '</a></li>';
                continue;
            }

            if ((n == 1)) {
                html += '<li><a href="#" onclick="loadpage('+ n +'); return false;">' + n + '</a></li>';
                continue;
            }
        }
        if (curpage != pages) {
           html += '<li><a href="#" onclick="loadpage('+ pages +'); return false;">' + pages + '</a></li>';
           html += '<li><a href="#" onclick="loadpage('+ (curpage + 1) +'); return false;">Next</a></li></ul>';
        }
        else {
            html += '<li class="disabled"><a href="#">Next</a></li></ul>';
        }

        $('#pagenavtop').html(html);
        $('#pagenavbot').html(html);
        })
        .fail(function( jqxhr, textStatus, error ) {
            if(document.getElementById("ErrorModal")){
                // we already injected the modal before
                $('#ErrorModal').modal('show');
                return;
            }
            $('body').append('<div id="ErrorModal" class="modal fade" tabindex="-1" role="dialog" aria-labelledby=\
                "Connection Lost" aria-hidden="true">\
                <div class="modal-header">\
                <button type="button" class="close" data-dismiss="modal" aria-hidden="true">×</button>\
                <h3 id="myModalLabel">Error</h3>\
                </div>\
                <div class="modal-body">\
                <p>Connection to server was lost ...</p>\
                </div>\
                <div class="modal-footer">\
                <button class="btn" data-dismiss="modal" aria-hidden="true">Close</button>\
                </div>\
                </div>');
            $('#ErrorModal').modal('show');
        });
        };

function loadpage(page) {
    offset = (page * window.perpage) - window.perpage;
    if (offset == 0) {
        window.updatetimer = setInterval(function(){getlog();},60000);
    }
    else {
        clearInterval(window.updatetimer);
    }
    window.offset = offset;
    getlog(window.offset);
    return
}