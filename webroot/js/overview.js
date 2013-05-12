function update() {
        $('#spinner').show();
        $.getJSON('/rpc.cgi?type=overview', function(data) {
            var html = "";
            $.each(data['log'], function(key, item) {
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
            });
            $.each(data['status'], function(key, value) {
                document.getElementById(key).innerHTML = value;
                });
        });
        $('#spinner').hide();
        };
