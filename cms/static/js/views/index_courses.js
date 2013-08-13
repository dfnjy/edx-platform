function indexCourses(){
    $("body").css("cursor", "progress");
    var course = "";
    var url = "http://" + window.location.host + "/index";
    var courseTitle = $("#index-courses").eq(0).attr("data-course");
    $.ajax({
        type: "POST",
        url: url,
        data: {"course": courseTitle},
        success: success
    });
}

function success(){
    $("body").css("cursor", "auto");
    console.log("Success!");
}

$(document).ready(function() {
    $("#index-courses").unbind();
    $("#index-courses").eq(0).bind("click", indexCourses);
});
