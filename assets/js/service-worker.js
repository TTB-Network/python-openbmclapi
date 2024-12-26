self.addEventListener('install', function(event) {
})
self.addEventListener('push', function (event) {
    event.waitUntil(
      self.registration.showNotification('新消息', {
        body: '你有一条新消息，请查看！',
        icon: 'icon.png',
        vibrate: [200, 100, 200],
        data: {
          url: 'https://your-website.com/message'
        }
      })
    );
  });