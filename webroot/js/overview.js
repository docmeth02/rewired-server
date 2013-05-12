function update() {
        $.getJSON('/rpc.cgi?type=shortlog', function(data) {
            $('#spinner').show();
            if (data.hasOwnProperty('success')) {
                alert('YUP');
            }
            var items = [];
            var html = "";
            $.each(data, function(key, item) {
                var row = '<tr><td>'+ item['DATE']+'</td><td>'+ item['STRING'];
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
                        default:
                            type = 'label-info';
                    }
                    row += '<span class="label '+ type + '">' + item['RESULT'] + '</span>';
                }
                row += '</td><td>' + item['USER'] + '</td></tr>';
                html += row;
            $('#log > tbody').html(html);
            $('#spinner').hide();
            });
        });
        };
