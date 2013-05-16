function getlog() {
        $.getJSON('/rpc.cgi?type=log&offset=' + window.offset)
        .done(function(data) {
            var html = "";
            var exten = 0;
            var users = 0;
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
                            type = 0;
                    }
               }
                if (item.hasOwnProperty('EXTENDED')) {
                row += '<tr '+ rowclass + 'onmouseover="$(\'#log' + exten + '\').collapse(\'show\');"\
                onmouseout="$(\'#log' + exten + '\').collapse(\'hide\');" onclick="$(\'#log\
                '+ exten + '\').collapse(\'toggle\');">';
                }
                else {
                    row += '<tr ' + rowclass + '>';
                }
                row += '<td style="max-width=60px;">'+ item['DATE']+'</td>';


                if (item['USER'] != '-') {
                    row += '<td><span id="User' + users +'" login="'+ item['LOGIN']+ '">' + item['USER'] + '</span></td>';
                users ++;
                }
                else {
                    row += '<td>' + item['USER'] + '</td>';
                    }
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
                    if (type){
                        row += '<td><span class="label '+ type + '">' + item['RESULT'] + '</span></td>';
                    }
                    else {
                        row += '<td>' + item['RESULT'] + '</td>';
                    }
                }
                else {
                    row += '<td></td>';
                }
                row += '</tr>'
                html += row;

            $('#log > tbody').html(html);
            for (var i=0;i<users;i++) {
                $('#User' + i).popover({
                    trigger: 'manual',
                    position: 'bottom',
                    template: '<div class="popover moocow"><div class="arrow"></div><div class="popover-inner">\
                    <h3 class="popover-title"></h3><div class="popover-content"><p></p></div></div></div>',
                    html: true,
                    title: '',
                    content: ''
                    }).click(function(evt) {
                        evt.stopPropagation();
                        if ($(this).next('div.popover:visible').length) {  // check for close event
                        $(this).popover('hide');
                        }
                        else {
                            $.getJSON('/rpc.cgi?type=userinfo&login=' + $(this).attr('login'), target = $(this))
                            .done(function(data) {
                                popover = target.data('popover');
                                popover.options.title = '<h4><img src="data:image/png;base64,' + data['image'] +'" \
                                alt="User Icon" style="padding-right:5px;" width="32" height="32"/>\ User ' +target.attr('login') +'</h4>';
                                popover.options.content = '<div class="container-fluid">\
                                <div class="span7">\
                                <div class="row-fluid">\
                                <div class="span7">\
                                <table class="table">\
                                <thead></thead>\
                                <tbody>\
                                <tr><td>Last seen: </td>\
                                <td>'+ data['lastseen'] + '</td></tr>\
                                <tr><td>Last IP: </td>\
                                <td>'+ data['ip'] + '</td></tr>\
                                <tr><td>Uploaded: </td>\
                                <td>' + data['upload'] + '</td></tr>\
                                <tr><td>Downloaded: </td>\
                                <td>' + data['download'] + '</td></tr>\
                                <tr><td>Ratio: </td>\
                                <td>' + data['ratio'] + '</td></tr>\
                                </tbody>\
                                </table>\
                                </div>\
                                </div>\
                                </div>\
                                </div>';
                                target.popover('show');
                            })
                            .fail(function( jqxhr, textStatus, error ) {
                                alert("Fail");
                            });
                            }
                    });
            }
    $(document).click(function (e)
      {
          if ($(e.target).parents('.popover').length == 0) $('[data-original-title]').popover('hide');
      });
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
