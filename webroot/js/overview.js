function update() {
        $('#spinner').show();
        $.getJSON('/rpc.cgi?type=overview')
        .done(function(data) {
            var html = "";
            $.each(data['log'], function(key, item) {
                var row = '<tr><td>'+ item['DATE']+'</td><td style="word-wrap: break-word; word-break: break-all;">'+ item['STRING'];
                if (item.hasOwnProperty('RESULT')) {
                    var type = ""
                    switch(item['RESULT']) {
                        case 'ok':
                            type = 'label-success';
                            break;
                        case 'complete':
                            type = 'label-success';
                            break;
                        case 'aborted':
                            type = 'label-important';
                            break;
                        case 'failed':
                            type = 'label-important';
                            break;
                        default:
                            type = 'label-info';
                    }
                    row += '<span class="label '+ type + '">' + item['RESULT'] + '</span>';
                }
                row += '</td><td>' + item['USER'] + '</td></tr>';
                html += row;

            $('#log > tbody').html(html);
            });
            $.each(data['status'], function(key, value) {
                document.getElementById(key).innerHTML = value;
                });
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
        $('#spinner').hide();
        };
