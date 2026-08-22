
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head id="Head1"><title>
	::PrevFiling Info::
</title>
    <base target="_self" />

    <script src="../CompuOfficeV2/js/jquery-1.9.1.min.js" type="text/javascript"></script>
    <script type="text/javascript" language="javascript" src="../Master/Script/showDialogPopup.js"></script>
    <script language="javascript" type="text/javascript">
    function PagLoad(HdnDispDvN,dvF,dvSec)
    {
        //alert(document.getElementById(HdnDispDvN).value);
        if(document.getElementById(HdnDispDvN).value=="1")
            document.getElementById(dvSec).style.display='none';
        else
            document.getElementById(dvF).style.display='none';
    }
    
    function CheckMandatory(FilingDate,PRN)
    {
        PRN.value=trimString(PRN.value);
        if(FilingDate.value=='')
        {
            alert('Please Enter Filing Date');return false;
        }
        if(PRN.value=='' || PRN.value.length<15)
        {
        alert('Please Enter Correct PRN');return false;
        }
        //alert(event.srcElement.);
        $("#DivWorking").show();
        $("#loderImg").show();
    }
    function CloseFormOnClick(returnValue)
    {
        if (window.opener != undefined)
            window.opener.returnValue = 1;
        else
            window.returnValue = 1;
       
        window.close();
        
        //window.parent.SetRegularReturnProcess(returnValue);
        
    }
    </script>

    <script language="javascript" type="text/javascript" src="Form26/JvScript/JsDate.js"></script>

    <link type="text/css" rel="stylesheet" href="css/innerpages.css" /></head>
<body class="innerBack" style="min-width: 99%" onkeydown="SetCursor();">
    <form method="post" action="./PrevFilingInfo.aspx" id="form1">
<div class="aspNetHidden">
<input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="/wEPDwUKMjA5OTUwMTc0Ng9kFgICAw9kFggCAQ8PFgIeBFRleHQFGUhBTUlEQSBBS0JBUiBSQVROQU5JLShUMSlkZAIDDw8WAh8ABT1RdWFydGVyIDogMiBGcm9tIDogMDEvSnVsLzIwMjUgVG8gOiAzMC9TZXAvMjAyNSBBLlkgMjAyNi0yMDI3ZGQCBQ8PZBYCHgVTdHlsZQUTdmlzaWJpbGl0eTp2aXNpYmxlO2QCBw9kFggCAQ8PFgIfAAXDAUFjY29yZGluZyB0byByZXR1cm4gZmlsbGluZyBlbnRyeSwgZGV0YWlsIG9mIGltbWVkaWF0ZSBwcmV2aW91cyByZWd1bGFyIHN0YXRlbWVudCBmb3IgZm9ybSAyNlEgaXMgYXMgZm9sbG93cy4gSWYgaXQgaXMgbm90IGNvcnJlY3QgdGhlbiBraW5kbHkgZW50ZXIgZGV0YWlsIG9mIGltbWVkaWF0ZSBwcmV2aW91cyByZWd1bGFyIHN0YXRlbWVudGRkAgcPEGQQFRQJMjAyNy0yMDI4CTIwMjYtMjAyNwkyMDI1LTIwMjYJMjAyNC0yMDI1CTIwMjMtMjAyNAkyMDIyLTIwMjMJMjAyMS0yMDIyCTIwMjAtMjAyMQkyMDE5LTIwMjAJMjAxOC0yMDE5CTIwMTctMjAxOAkyMDE2LTIwMTcJMjAxNS0yMDE2CTIwMTQtMjAxNQkyMDEzLTIwMTQJMjAxMi0yMDEzCTIwMTEtMjAxMgkyMDEwLTIwMTEJMjAwOS0yMDEwCTIwMDgtMjAwORUUCTIwMjctMjAyOAkyMDI2LTIwMjcJMjAyNS0yMDI2CTIwMjQtMjAyNQkyMDIzLTIwMjQJMjAyMi0yMDIzCTIwMjEtMjAyMgkyMDIwLTIwMjEJMjAxOS0yMDIwCTIwMTgtMjAxOQkyMDE3LTIwMTgJMjAxNi0yMDE3CTIwMTUtMjAxNgkyMDE0LTIwMTUJMjAxMy0yMDE0CTIwMTItMjAxMwkyMDExLTIwMTIJMjAxMC0yMDExCTIwMDktMjAxMAkyMDA4LTIwMDkUKwMUZ2dnZ2dnZ2dnZ2dnZ2dnZ2dnZ2dkZAILDw8WAh8ABQszMC1NYXktMjAyNmRkAg0PDxYCHwAFDzc3MDAwMDM4OTc1ODQwMWRkGAEFHl9fQ29udHJvbHNSZXF1aXJlUG9zdEJhY2tLZXlfXxYCBQ10eHRGaWxpbmdEYXRlBQZ0eHRQUk5MXBDNI4dFWk/QePU+QDBVBrcnl8bxms3zl1EKIW8sGA==" />
</div>


<script src="/WebResource.axd?d=DgpmlnIWD-787fIxlNBRIfG34f_HmqfQc5J9qMUpVC4SN_sDlZ-onPAS9nzPZrFtzmaDvScHpTANQK80lgAVHdEomxuGvR58pL8NA4bWGAVEeyI3KS287AlYtLwXH8L771lYu1gJbx5dqS-LIRSa4A2&amp;t=638755834460000000" type="text/javascript"></script>
<div class="aspNetHidden">

	<input type="hidden" name="__VIEWSTATEGENERATOR" id="__VIEWSTATEGENERATOR" value="1C0D0069" />
	<input type="hidden" name="__EVENTVALIDATION" id="__EVENTVALIDATION" value="/wEdACH1dAf1bMzh2vPa/yXV5hhwmW/ynBkkkA2xI95ik8Vs4NfNomC1TSzUyLmb7z+vo2d8bbBq2qXGyD56reBvhFcEn4BUj3ayriONUW1LfYiby1bR1ko5Tg4QRCbn6zWhy2Qw4AHISFelPw7EOdidPrcNRD6urn0rZdNuXUglQYNkz03FAmJMxT+qGNqVSz/e+v4j5VnpTKFpnkD29yPWP+OCZhT7k6lUMcEgY9uZVayfDDqTkLOrQdA3BNvVkTon8HJSj4wr3OhUIxcygGLhrncw6S+vd6VityQ/OE4ALmh0c1+iQ+up2eeEn+x+yGu6DZi+omMfh6L6Igux+A3/+OxluOHy1aUf/NOTFAM44Ink0K5+oZGbtudp77Q9foMTUJKahuVIy1vbXmhsxDJfQMsz/3YmdNwUDTUj+00TjFh89qW3ZkM663tX1vy25gJLCHQXKBw32UGMIMh4SG30FAof7BChFmQVzhJNEB1dVQ2W44esjxA9FCbsH+45CKH158MT5j0kUUpj+aCEJI8u3KElpxXuPo2Al7NV6ltiGdjqvW/KRIQVhoyM2eNZsq0+ZTXW00hovM2SbcMImuKcGxbv3+cCId25P61oKMFqSwhXbdZ6XXixBsSI51fpPXeJX10R+Oo31JSA5azGO39Mz7YrpkYebWIKh1f+oMa+s8OlvU3V4z4KDmou8xkVsVZ0DiWWhBUiZDcLOPqoFGjYNJYCJBE395kBT7T2C95ZSVeZdQ==" />
</div>
        <div class="commonboxContent">
            <div class="pagesHeading">
                <table cellpadding="0" cellspacing="0" class="width100">
                    <tr>
                        <td class="tL width25">
                            <span id="lblCompanyInfo">HAMIDA AKBAR RATNANI-(T1)</span>
                        </td>
                        <td class="tC">
                            <span id="lblQuarterDetail">Quarter : 2 From : 01/Jul/2025 To : 30/Sep/2025 A.Y 2026-2027</span>
                        </td>
                        <td class="tR" width="150">
                            <input type="submit" name="BtnSave" value=" " onclick="return CheckMandatory(txtFilingDate,txtPRN);" id="BtnSave" class="cont_btn" style="visibility:visible;" />
                        </td>
                    </tr>
                </table>
            </div>
            <div id="dvF">
                <div class="box">
                    <table cellpadding="0" class="width99" align="center" cellspacing="0">
                        <tr>
                            <td>
                                <span id="lblMsg">According to return filling entry, detail of immediate previous regular statement for form 26Q is as follows. If it is not correct then kindly enter detail of immediate previous regular statement</span>
                            </td>
                            <td class="aButton tR">
                                <input type="submit" name="BtnCancel" value="Cancel" onclick="javascript:CloseFormOnClick(0);" id="BtnCancel" style="margin-bottom: 10px;" />
                                <input type="submit" name="BtnDelete" value="Delete" id="BtnDelete" style="margin-bottom: 10px;" />
                            </td>
                        </tr>
                    </table>
                </div>
                <div class="box boxStyle commonTabel" style="height: 150px;">
                    <table cellpadding="5" class="width99" align="center" cellspacing="0">
                        <tr>
                            <th class="width20">
                                Assessment Year
                            </th>
                            <th class="width20">
                                Quarter
                            </th>
                            <th class="width20">
                                Date
                            </th>
                            <th class="width40 tC">
                                PRN
                            </th>
                        </tr>
                        <tr class="tC">
                            <td>
                                <select name="CmbYear" id="CmbYear" class="width98">
	<option value="2027-2028">2027-2028</option>
	<option selected="selected" value="2026-2027">2026-2027</option>
	<option value="2025-2026">2025-2026</option>
	<option value="2024-2025">2024-2025</option>
	<option value="2023-2024">2023-2024</option>
	<option value="2022-2023">2022-2023</option>
	<option value="2021-2022">2021-2022</option>
	<option value="2020-2021">2020-2021</option>
	<option value="2019-2020">2019-2020</option>
	<option value="2018-2019">2018-2019</option>
	<option value="2017-2018">2017-2018</option>
	<option value="2016-2017">2016-2017</option>
	<option value="2015-2016">2015-2016</option>
	<option value="2014-2015">2014-2015</option>
	<option value="2013-2014">2013-2014</option>
	<option value="2012-2013">2012-2013</option>
	<option value="2011-2012">2011-2012</option>
	<option value="2010-2011">2010-2011</option>
	<option value="2009-2010">2009-2010</option>
	<option value="2008-2009">2008-2009</option>

</select>
                            </td>
                            <td>
                                <select name="CmbQuarter" id="CmbQuarter" class="width98">
	<option value="1">1st (Apr-Jun)</option>
	<option value="2">2nd (Jul-Sep)</option>
	<option value="3">3rd (Oct-Dec)</option>
	<option selected="selected" value="4">4th (Jan-Mar)</option>

</select>
                            </td>
                            <td>
                                &nbsp;<input name="txtFilingDate" type="text" value="30-May-2026" maxlength="10" size="11" id="txtFilingDate" onfocus="dateonfocus(&#39;txtFilingDate&#39;,2,&#39;-&#39;);" onblur="dateonleave(&#39;txtFilingDate&#39;,2,&#39;-&#39;);" onkeyup="enterdata(&#39;txtFilingDate&#39;,2,&#39;-&#39;);" onkeydown="beforeenter(&#39;txtFilingDate&#39;,&#39;-&#39;);" style="border-color:Gray;border-width:1px;border-style:Solid;" /></td>
                            <td>
                                <input name="txtPRN" type="text" value="770000389758401" maxlength="15" id="txtPRN" onkeypress="return IsNumberInput(&#39;txtPRN&#39;,0);" style="border-color:Gray;border-width:1px;border-style:Solid;text-align:Right;" />
                            </td>
                        </tr>
                    </table>
                    <table cellpadding="5" class="width99" align="center" cellspacing="0">
                        <tr>
                            <td>
                                If no any previous regular statement for this form, click on delete
                            </td>
                        </tr>
                    </table>
                </div>
            </div>
            <div id="dvSec">
                <center>
                    <table cellpadding="4" class="width99" align="center" cellspacing="4">
                        <tr>
                            <td>
                                <span id="lblMsg1"></span>
                            </td>
                        </tr>
                        <tr>
                            <td class="tL redC">
                                <span id="lblN">Whether regular statement for Form 26Q Not filed for earlier period ?</span>
                            </td>
                            <td class="aButton tL">
                                <input type="submit" name="BtnYes" value="Yes" onclick="javascript:dvF.style.display=&#39;&#39;;dvSec.style.display=&#39;none&#39;;BtnSave.style.visibility=&#39;visible&#39;;return false;" id="BtnYes" />
                                <input type="submit" name="BtnNo" value="No" onclick="javascript:window.returnValue=1;window.close();" id="BtnNo" />
                            </td>
                        </tr>
                    </table>
                </center>
            </div>
            <div class="box boxStyle blueC">
                <span id="lblNote">Note: PRN of immediate previous accepted regular statement of same Form (if any) is mandatory in regular return.</span>
            </div>
        </div>
        <input type="hidden" name="HdnDispDvN" id="HdnDispDvN" value="1" />
        <div id="DivWorking" style="display: none;">
            Please Wait...</div>
        <div id="loderImg">
            Please wait... Processing
        </div>
    

<script type="text/javascript">
//<![CDATA[
PagLoad('HdnDispDvN','dvF','dvSec');//]]>
</script>
</form>
</body>
</html>
