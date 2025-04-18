$(function () {
    let isSendingCode = false; // 防止重复发送

    $('#send-verification-btn').on('click', function () {
        if (isSendingCode) return;

        isSendingCode = true;
        const email = $("input[name='email']").val().trim();

        if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
            showErrorMessage('请输入正确的邮箱地址');
            setTimeout(() => hideErrorMessage(), 2000);
            isSendingCode = false;
            return;
        }

        $.ajax({
            url: "/mail/captcha?email=" +  encodeURIComponent(email),
            method: 'GET',
            success: function () {
                sendCodeSuccess();
            },
            error: function () {
                showErrorMessage('验证码发送失败，请稍后再试');
                setTimeout(() => hideErrorMessage(), 2000);
            }
        });
    });

    function sendCodeSuccess() {
        let btn = $('#send-verification-btn');
        btn.addClass('disabled');
        btn.text('已发送');

        let countDown = 60;
        const interval = setInterval(() => {
            if (countDown > 0) {
                btn.text(`重新发送（${countDown}）`);
                countDown--;
            } else {
                clearInterval(interval);
                btn.removeClass('disabled');
                btn.text('发送验证码');
                isSendingCode = false;
            }
        }, 1000);
    }

    function showErrorMessage(message) {
        const modal = $('#errorModal');
        modal.find('.modal-body').text(message);
        modal.modal('show');
    }

    function hideErrorMessage() {
        $('#errorModal').modal('hide');
    }
});