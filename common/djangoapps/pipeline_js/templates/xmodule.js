define(["jquery", "youtube", "mathjax", "codemirror", "tinymce", "jquery.tinymce"], function($, YT, MathJax, CodeMirror, tinyMCE) {
    window.$ = $;
    window.YT = YT;
    window.MathJax = MathJax;
    window.CodeMirror = CodeMirror;
    window.tinyMCE = tinyMCE;
    window.RequireJS = {
        'requirejs': requirejs,
        'require': require,
        'define': define
    };

    var urls = ${urls};
    var head = $("head");
    $.each(urls, function(i, url) {
        head.append($("<script/>", {src: url}));
    });
    return window.XModule;
});
