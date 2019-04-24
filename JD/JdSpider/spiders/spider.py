# -*- coding: utf-8 -*-
import scrapy
import os
import re
from scrapy_splash import SplashRequest #用于爬取动态网页数据
import urllib.request # 这是用来下载图片，不使用scrapy下载
from urllib.parse import quote  # 这里是利用quote将汉字转化为url编码
import requests
import json

# docker run -p 8050:8050 scrapinghub/splash
class SpiderSpider(scrapy.Spider):
    name = 'spider'
    allowed_domains = ['jd.com']
    start_urls = ['https://www.jd.com/allSort.aspx']

    # 默认抓取其实页面的信息, 获取商品的种类，比如：手机，电脑，平板等等
    def parse(self, response):
        xpathsList = [
            "/html/body/div[5]/div[2]/div[1]/div[2]/div[1]/div[2]/div[2]/div[3]/dl[1]/dd/a[1]"
        ]
        # "/html/body/div[5]/div[2]/div[1]/div[2]/div[1]/div[3]/div[2]/div[3]/dl[1]/dd/a",
        # "/html/body/div[5]/div[2]/div[1]/div[2]/div[1]/div[6]/div[2]/div[3]/dl[4]/dd/a"
        goodsList = []
        urlsList = []

        for xpaths in xpathsList:
            content = response.xpath(xpaths)
            goodsList = goodsList + content.xpath("./text()").extract()
            urlsList = urlsList + content.xpath("./@href").extract()
        
        # 获取目录信息，以便每次循环建立文件夹
        os.chdir("JDdata")
        goodsDir = os.getcwd();
        i = 0
        while (i<len(goodsList)):
            goodsList[i] = re.sub(r'/', ' ', goodsList[i])  # 将不合法的文件夹名称改为合法的
            if os.path.exists(goodsList[i]) == False:
                os.mkdir(goodsList[i])  # 创建目录
            i = i+1
        # 使用回调函数
        i = -1
        for url in urlsList:
            i = i+1
            url = "https:" + url
            dir = goodsDir + "\\" + goodsList[i]
            yield scrapy.Request(url, callback=self.parseBrands, meta={'goodsDir':dir} )


    # 抓取每种商品各个品牌的信息，例如手机包含：华为，小米，三星，苹果等等
    def parseBrands(self, response):
        if response.status==200:
            brandUrls = []
            brandNames = []
            os.chdir(response.meta['goodsDir'])
            brandsDir = os.getcwd()
            brandsLists = response.xpath("//*[@id='brandsArea']/li")
            for brand in brandsLists:
                brandUrl = brand.xpath("./a/@href").extract_first()
                brandUrls.append(brandUrl)
                brandName = brand.xpath("./a/@title").extract_first()
                brandNames.append(brandName)
                if os.path.exists(brandName) == False:
                    os.mkdir(brandName)     # 创建目录
            
            i = -1
            for url in brandUrls:
                i = i+1
                url = "https://list.jd.com" + url + "#J_crumbsBar"  #特别注意这里的url中包含中文以及中文符号，需要转化为url编码
                url = self.zhUrl(url)
                dir = brandsDir + "//" + brandNames[i]
                # 使用 SplashRequest 抓取动态网页
                yield SplashRequest(url=url, callback=self.parseTypes, args={'wait': 1}, meta={'brandDir':dir})
    
    # 抓取各个品牌不同型号，例如华为手机包含：huawei p30 pro， huawei mate20 pro等等
    def parseTypes(self, response):
        if response.status == 200:
            typesUrls = []
            productID = []
            os.chdir(response.meta['brandDir'])
            # open("test.html",'wb+').write(response.body)
            typesDir = os.getcwd()
            contents = response.xpath("//*[@id='plist']/ul/li")
            for content in contents:
                isJDSelf = content.xpath("./div/div[8]/i[1]/text()").extract_first()
                if isJDSelf == "自营":  #仅仅抓取京东自营的商品
                    typeUrl = content.xpath("./div/div[1]/a/@href").extract_first()
                    typesUrls.append(typeUrl)
                    product = content.xpath("./div/@data-active-sku").extract_first()
                    productID.append(product)
            
            i =-1
            for url in typesUrls:
                i = i+1
                id = productID[i]
                url = "https:" + url
                yield SplashRequest(url=url, callback=self.parseColors, args={'wait': 1}, meta={'typeDir':typesDir, 'productID':id})

    # 抓取不同型号商品的不同颜色，例如 huawei p30 pro 包含天空之境，珠光贝母等等
    def parseColors(self,response):
        if response.status == 200:
            colors = []
            colorsUrlsID = []
            os.chdir(response.meta['typeDir'])
            type = response.xpath("//*[@id='crumb-wrap']/div/div[1]/div[9]/@title").extract_first()
            if os.path.exists(type) == False:
                    os.mkdir(type)     # 创建目录
                    os.chdir(type)
                    colorDir = os.getcwd()
                    # 调用抓取评论的函数
                    commentUrl = "https://sclub.jd.com/comment/productPageComments.action?callback=myCommentsJson&productId=" + response.meta['productID'] + "&score=0&sortType=5&page=0&pageSize=10&isShadowSku=0&rid=0&fold=1"
                    yield scrapy.Request(commentUrl, callback=self.parseComments, meta={'productID':response.meta['productID'], 'dir': colorDir})

                    # colorSelectors = response.xpath("//*[@id='choose-attr-1']/div[2]/div")
                    # for colorSelector in colorSelectors:
                    #     color = colorSelector.xpath("./@data-value").extract_first()
                    #     colors.append(color)
                    #     colorUrlID = colorSelector.xpath("./@data-sku").extract_first()
                    #     colorsUrlsID.append(colorUrlID)
                    # i = -1
                    # for colorID in colorsUrlsID:
                    #     i = i+1
                    #     name = type + " " + colors[i]
                    #     colorUrl  = "https://item.jd.com/" + colorID + ".html#crumb-wrap"
                    #     yield SplashRequest(url=colorUrl, callback=self.parseImgs, meta={'colorDir':colorDir, 'name':name})
    
    # 抓取图片
    def parseImgs(self, response):
        if response.status == 200:
            os.chdir(response.meta['colorDir'])
            imgName = response.meta['name'] + ".jpg"
            if os.path.isfile(imgName) == False:
                imgUrl = response.xpath("//*[@id='spec-img']/@src").extract_first()
                imgUrl = "https:" + imgUrl
                self.downloadImg(imgUrl, imgName, dir)

    # 抓取评论
    def parseComments(self, response):
        if response.status == 200:
            if len(response.text) != 0:
                filename = response.meta['dir'] + "//" + "comment.txt"
                commentFile = open(filename, 'a+')
                content = response.text
                content = content.replace('myCommentsJson(', '')
                content = content.replace(');', '')
                jsonContent = json.loads(content)
                maxPage = jsonContent["maxPage"]
                pageNum = 0
                while (pageNum <maxPage):
                    commentUrl = "https://sclub.jd.com/comment/productPageComments.action?callback=myCommentsJson&productId=" + response.meta['productID'] + "&score=0&sortType=5&page=" + str(pageNum) + "&pageSize=10&isShadowSku=0&rid=0&fold=1"
                    reqResponse = requests.get(commentUrl)
                    content = reqResponse.text
                    content = content.replace('myCommentsJson(', '')
                    content = content.replace(');', '')
                    jsonContent = json.loads(content)
                    i=0
                    while (i<10):
                        text = ((jsonContent["comments"])[i])["content"]
                        text = text.replace('\n',";") + '\n'
                        print("************************")
                        print(text)
                        commentFile.write(text)
                        i = i+1
                    pageNum = pageNum+1
        return

    # 下载图片的函数
    def downloadImg(self, imgUrl, imgName, dir):
        apiToken = "fklasjfljasdlkfjlasjflasjfljhasdljflsdjflkjsadljfljsda"
        header = {"Authorization": "Bearer " + apiToken} # 设置http header
        request = urllib.request.Request(imgUrl, headers=header)
        try:
            response = urllib.request.urlopen(request)
            if response.getcode() == 200:
                with open(imgName, "wb") as f:
                    f.write(response.read())    # 将内容写入图片
                return imgName
        except:
            print("***********ERROR***********")
    
    # 中文转url编码函数
    def zhUrl(self, url):
        i = 0
        result = ""
        flag = []
        pa = re.compile(u'[\u4E00-\u9FA5（）]')
        while(i<len(url)):
            if pa.findall(url[i]) != flag:
                result = result + urllib.parse.quote(url[i])
            else:
                result = result + url[i]
            i=i+1
        return result
